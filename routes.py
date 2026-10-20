"""The 16 Cutshort endpoints. Every path is served with and without the
`/cutshort` prefix, so code generated against the hosted API (paths like
/jobs/details) runs unchanged against this server.

Params are validated by the marshmallow schemas in cutshort/schemas.py, the
same ones the hosted API uses: ONE param per input — `job` takes a job link,
slug or ID, `company` a name, link or alias, `query` free text or a listing
link, `location` any spelling of a city."""
import json
from urllib.parse import urlencode

from bottle import request, response, route

from cutshort import companies, jobs, lookups, salaries, schemas
from schema_fields import load_query
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The request query as unicode strings (bottle 0.12's .get() hands back
    latin-1 decoded bytes, so a UTF-8 "Amélie" would arrive as "AmÃ©lie")."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def _page_link(params, page):
    if not page:
        return None
    query = {k: v for k, v in params.items() if v not in (None, "", False)}
    query["page"] = page
    parts = request.urlparts
    return f"{parts.scheme}://{parts.netloc}{parts.path}?{urlencode(query, doseq=True)}"


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate(result, raw_params):
    """Lift the scraper's `pagination` block into the flat shape of the hosted
    API (count / per_page / current_page / total_pages / next / previous)."""
    pagination = result.pop("pagination", None) or {}
    result.pop("count", None)
    page = _as_int(pagination.get("page")) or _as_int(raw_params.get("page")) or 1
    total_pages = max(_as_int(pagination.get("total_pages")), 0)
    out = {
        "count": pagination.get("total_count"),
        "per_page": pagination.get("items_per_page"),
        "current_page": page,
        "total_pages": total_pages,
        "next": _page_link(raw_params, page + 1 if page < total_pages else None),
        "previous": _page_link(raw_params, page - 1 if page > 1 else None),
    }
    out.update(result)
    return out


def call(label, schema, impl, paginated=False):
    """Validate the query, run the scraper function and map failures:
    bad params -> 400, missing job / company / page -> 404,
    blocked / upstream failure -> 502, anything else -> 500."""
    raw = query_dict()
    data, error = load_query(schema, raw)
    if error:
        return json_response(error, 400)
    try:
        result = impl(**data)
    except ValueError as e:
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:
        return json_response({"error": f"cutshort rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Blocked as e:
        return json_response({"error": f"cutshort blocked the request, retry later: {e}"}, 502)
    except UpstreamError as e:
        return json_response({"error": f"cutshort {label} failed: {e}"}, 502)
    except Exception as e:
        return json_response({"error": f"cutshort {label} failed: {type(e).__name__}: {e}"}, 500)
    if paginated:
        result = paginate(result, raw)
    return json_response(result)


def mount(path, schema, impl, paginated=False):
    """Serve one endpoint at /path and /cutshort/path."""
    def handler():
        return call(path.strip("/"), schema, impl, paginated)
    handler.__name__ = "cutshort_" + path.strip("/").replace("/", "_").replace("-", "_")
    route(path, method="GET")(handler)
    route("/cutshort" + path, method="GET")(handler)
    return path


ENDPOINTS = [
    # jobs
    mount("/jobs/details", schemas.JobSchema, jobs.details),
    mount("/jobs/search", schemas.JobSearchSchema, jobs.search, paginated=True),
    mount("/jobs/batch", schemas.JobBatchSchema, jobs.batch),
    mount("/jobs/similar", schemas.SimilarJobsSchema, jobs.similar),
    # companies
    mount("/companies/details", schemas.CompanySchema, companies.details),
    mount("/companies/jobs", schemas.CompanyJobsSchema, companies.open_jobs, paginated=True),
    mount("/companies/search", schemas.CompanySearchSchema, companies.search),
    mount("/companies/directory", schemas.DirectorySchema, companies.directory, paginated=True),
    # salaries + content
    mount("/salaries", schemas.SalarySchema, salaries.details),
    mount("/job-descriptions/details", schemas.JobDescriptionSchema, lookups.job_description),
    # lookups
    mount("/autocomplete", schemas.AutocompleteSchema, lookups.autocomplete),
    mount("/jobs/categories", schemas.CategoriesSchema, jobs.categories, paginated=True),
    mount("/companies/categories", schemas.DirectoryCategoriesSchema, companies.categories),
    mount("/salaries/titles", schemas.SalaryTitlesSchema, salaries.titles),
    mount("/job-descriptions", schemas.EmptySchema, lookups.job_descriptions),
    mount("/locations", schemas.EmptySchema, lookups.locations),
]


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": ENDPOINTS})
