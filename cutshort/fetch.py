"""Cutshort transport: plain curl_cffi, no browser, validated 2026-10-19
from a direct India egress with no cookies and no login.

Surfaces (all on cutshort.io; the Next.js site's own JSON backend answers
an anonymous client — Cloudflare fronts it with a 4-hour edge cache and no
challenge, 40 parallel calls from one IP all 200):

  listing(slug, page)         /backend-api/webpage/jobs/<slug>?page=N — a job
                              listing page: 50 cards newest first, liveJobCount,
                              the side links. `jobs_not_found` past the end,
                              `jobs_page_config_not_found` for a slug that is
                              not a listing.
  job(ref)                    /backend-api/webpage/job/<id-or-slug> — the full job
                              (description HTML, skills with codes, INR salary
                              band, experience band, remote policy, role types,
                              posted date, the company card); `job_not_found`.
  similar_jobs(id)            /get-similar-jobs?jobid=<_id>&listingComponent=true
  categories(page)            /backend-api/webpage/jobs?page=N — the 3,790
                              listing slugs, 15 a page.
  company(alias, page)        /backend-api/webpage/company/<alias>?page=N — the
                              company profile, 10 open jobs a page, similar
                              companies; `company_not_found`.
  directory(slug, page)       /backend-api/webpage/companies/<slug>?page=N — a
                              company directory, 50 a page;
                              `companies_not_found_in_db_for_search` past the end.
  job_description(slug)       /backend-api/webpage/job-description/<slug>
  sitemap()                   /backend-api/webpage/sitemap — every listing,
                              directory and salary page with its label.
  salary_page(title, loc)     the /salary/<title>/<location> HTML page — the
                              only surface with no JSON route; its
                              __NEXT_DATA__ carries the percentiles, trends,
                              FAQs and related pages. A role with no page
                              308-redirects to /check-salary-in-india.
  analytics(context, params)  /api/get-analytics-data/<context> (salary trends).
  algolia(index, query, n)    the search box's Algolia indices (skills,
                              companies, job titles, locations; public
                              search-only key).

Egress: every call rides a proxy exit (config.cutshort_proxy(): a sticky
residential exit in CUTSHORT_PROXY_COUNTRY). Cutshort is never
contacted from the server's own IP: with no proxy configured the call fails,
unless the config opts in with CUTSHORT_ALLOW_DIRECT = True (the open-source
kit does, for a user's own machine; the scrapers service never does). Each
worker thread keeps its exit and curl session between calls (keep-alive)
until a call fails; a 403 / 429 / 5xx / transport failure drops that exit and
the retry opens a fresh one. Uncached listing pages take ~10 s on the site's
side; the Cloudflare edge serves repeats in <1 s. The patchright
click-through (indeed/fetch.py _browser_page) is the escalation if a
challenge ever appears — not built while plain HTTP works.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  CutshortUpstreamError  transport failure / 5xx / unexpected body — retryable
  CutshortBlocked        429 / 403 / challenge                     — retryable on a new exit
  CutshortBadRequest     the site rejected the params (400)        — never retried
  CutshortNotFound       no such job / company / listing / page    — never retried
"""
import json
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from cutshort import refdata

IMPERSONATE = "chrome"
TIMEOUT = (10, 90)            # (connect, read): an uncached listing page takes the site ~10 s

JSON_HEADERS = {"accept": "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.9",
                "referer": f"{refdata.BASE_URL}/"}
HTML_HEADERS = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept-language": "en-US,en;q=0.9"}
CF_MARKERS = ("just a moment", "challenge-error-text", "cf-chl", "challenge-platform", "attention required")

WEBPAGE = "/backend-api/webpage"
NOT_FOUND_CODES = {"job_not_found", "company_not_found", "jobs_page_config_not_found", "companies_page_not_found",
                   "config_not_found", "page_config_not_found"}
PAST_END_CODES = {"jobs_not_found", "companies_not_found_in_db_for_search"}


class CutshortUpstreamError(UpstreamError):
    """Transport failure, 5xx or an unexpected body — retryable."""


class CutshortBlocked(CutshortUpstreamError, Blocked):
    """429 / 403 / challenge — retryable on a fresh exit."""


class CutshortBadRequest(BadRequest):
    """The site rejected the params — never retried."""


class CutshortNotFound(NotFound):
    """No such job / company / listing — never retried."""


class PastEnd(CutshortNotFound):
    """A page past the last one of a listing (the site's `jobs_not_found`)."""


def dump_debug(name, text):
    """Write a raw response to $CUTSHORT_DEBUG_DIR/<name>.txt for post-mortems."""
    dbg = os.environ.get("CUTSHORT_DEBUG_DIR", "")
    if dbg and text:
        try:
            os.makedirs(dbg, exist_ok=True)
            with open(os.path.join(dbg, name + ".txt"), "w") as f:
                f.write(text)
        except OSError:
            pass


# ---- curl sessions (per thread, keyed by exit) ---------------------------------------------------

_local = threading.local()


def _sessions():
    store = getattr(_local, "sessions", None)
    if store is None:
        store = _local.sessions = OrderedDict()
    return store


def _session(key, proxy):
    from curl_cffi import requests as curl_requests
    store = _sessions()
    sess = store.get(key)
    if sess is None:
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        store[key] = sess
        while len(store) > 4:
            _, old = store.popitem(last=False)
            try:
                old.close()
            except Exception:
                pass
    else:
        store.move_to_end(key)
    return sess


def _drop_session(key):
    sess = _sessions().pop(key, None)
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _proxy(fallback=False):
    """A new exit; refuses to go on without one (Cutshort never sees the
    server's own IP) unless the config opts in to direct egress."""
    proxy = config.cutshort_proxy(fallback=fallback)
    if not proxy and not getattr(config, "CUTSHORT_ALLOW_DIRECT", False):
        raise CutshortUpstreamError("no Cutshort proxy configured (Cutshort is never contacted from the server's IP)")
    return proxy


def _thread_exit():
    """This thread's current exit: reused across calls (one sticky IP, one
    keep-alive session) until a call on it fails."""
    if not hasattr(_local, "exit"):
        _local.exit = _proxy()
    return _local.exit


def _attempts(label, send):
    """Run send(session) under the retry policy: the first attempt rides the
    thread's exit, every retry a fresh one. CutshortUpstreamError (incl.
    Blocked) retries up to config.CUTSHORT_MAX_ATTEMPTS times; BadRequest /
    NotFound surface at once."""
    attempts = max(1, int(config.CUTSHORT_MAX_ATTEMPTS))
    last = None
    for attempt in range(1, attempts + 1):
        proxy = _thread_exit() if attempt == 1 else _proxy(fallback=True)
        key = proxy or "direct"
        sess = _session(key, proxy)
        try:
            return send(sess)
        except (CutshortBadRequest, CutshortNotFound):
            raise
        except CutshortUpstreamError as e:
            last = e
        except Exception as e:
            last = CutshortUpstreamError(f"request failed on {label}: {type(e).__name__}: {e}")
        _drop_session(key)
        if attempt == 1 and hasattr(_local, "exit"):
            del _local.exit                      # the next call starts on a fresh exit
        print(f"cutshort: attempt {attempt}/{attempts} on {label} failed: {last}")
        if attempt < attempts:
            time.sleep(1.0 * attempt)
    raise last


def is_challenged(status, headers, text):
    if (headers or {}).get("cf-mitigated") == "challenge":
        return True
    head = (text or "")[:4000].lower()
    return status in (403, 429, 503) and any(m in head for m in CF_MARKERS)


def _classify(resp, label, json_body=True, allow_redirect=False):
    """Raise the failure a response represents, else return its JSON (or text)."""
    status = resp.status_code
    headers = dict(resp.headers)
    text = resp.text or ""
    if is_challenged(status, headers, text):
        dump_debug("challenged", text)
        raise CutshortBlocked(f"challenge (HTTP {status}) on {label}")
    if status in (403, 429):
        raise CutshortBlocked(f"HTTP {status} on {label}")
    if status in (301, 302, 307, 308) and allow_redirect:
        raise CutshortNotFound(f"Cutshort has no page for {label}")
    if status in (404, 410):
        raise CutshortNotFound(f"Cutshort has no page for {label}")
    if status >= 500:
        raise CutshortUpstreamError(f"HTTP {status} on {label}")
    if status == 400 and json_body:
        body = _json_or_none(text)
        if body is not None:
            return body                     # the backend's envelope carries the error code
        raise CutshortBadRequest(f"Cutshort rejected the request on {label}: {text[:200]}")
    if status != 200:
        raise CutshortUpstreamError(f"HTTP {status} on {label}")
    if not json_body:
        return text
    body = _json_or_none(text)
    if body is None:
        dump_debug("non_json", text)
        raise CutshortUpstreamError(f"non-JSON answer on {label}")
    return body


def _json_or_none(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def _unwrap(body, label):
    """The backend envelope {"success", "data" | "error": {errorMsg, errorCode}}
    -> `data`; the error codes map to NotFound / PastEnd / BadRequest."""
    if not isinstance(body, dict):
        raise CutshortUpstreamError(f"unexpected payload on {label}")
    if body.get("success") and isinstance(body.get("data"), dict):
        return body["data"]
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = str(error.get("errorCode") or "")
    message = str(error.get("errorMsg") or body.get("message") or "no data")
    if code in PAST_END_CODES:
        raise PastEnd(f"Cutshort has no more results for {label}")
    if code in NOT_FOUND_CODES or code.endswith("_not_found"):
        raise CutshortNotFound(f"Cutshort has no page for {label}: {message}")
    if body.get("success") is False:
        raise CutshortBadRequest(f"Cutshort rejected the request on {label}: {message}")
    raise CutshortUpstreamError(f"unexpected payload on {label}")


def api_get(path, params=None, label=None, headers=None):
    """GET one JSON endpoint on the site -> its parsed body."""
    query = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}
    url = f"{refdata.BASE_URL}{path}" + (f"?{urlencode(query, doseq=True)}" if query else "")
    label = label or path

    def send(sess):
        resp = sess.get(url, headers={**JSON_HEADERS, **(headers or {})}, timeout=TIMEOUT)
        return _classify(resp, label)
    return _attempts(label, send)


def webpage(path, params=None, label=None):
    """GET /backend-api/webpage/<path> -> the envelope's `data`."""
    return _unwrap(api_get(f"{WEBPAGE}/{path.lstrip('/')}", params, label), label or path)


def html_get(path, label=None, allow_redirect_as_missing=False):
    """GET one HTML page on the site -> its text."""
    url = path if path.startswith("http") else f"{refdata.BASE_URL}{path}"
    label = label or path

    def send(sess):
        resp = sess.get(url, headers=HTML_HEADERS, timeout=TIMEOUT, allow_redirects=not allow_redirect_as_missing)
        return _classify(resp, label, json_body=False, allow_redirect=allow_redirect_as_missing)
    return _attempts(label, send)


# ---- jobs ------------------------------------------------------------------------------------------

def listing(slug, page=1):
    """One page of a job listing -> {seoData, pageContext, pageData{jobs,
    title, subTitle, sideJobLinks, breadcrumbs, liveJobCount}, meta}.
    PastEnd past the last page, CutshortNotFound for an unknown slug."""
    return webpage(f"jobs/{quote(slug)}", {"page": page} if page and page > 1 else None, f"listing {slug} p{page}")


def job(ref):
    """The full job record (the 8-char id, the 24-hex record id or the slug)."""
    return webpage(f"job/{quote(ref)}", label=f"job {ref}")


def similar_jobs(record_id):
    body = api_get("/get-similar-jobs", {"jobid": record_id, "listingComponent": "true"},
                   label=f"similar jobs of {record_id}")
    return body.get("jobs") if isinstance(body, dict) and isinstance(body.get("jobs"), list) else []


def categories(page=1):
    """One page (15) of the listing-slug index."""
    return webpage("jobs", {"page": page}, f"listing index p{page}")


# ---- companies -------------------------------------------------------------------------------------

def company(alias, page=1):
    return webpage(f"company/{quote(alias)}", {"page": page} if page and page > 1 else None,
                   f"company {alias} p{page}")


def directory(slug, page=1):
    return webpage(f"companies/{quote(slug)}", {"page": page} if page and page > 1 else None,
                   f"company directory {slug} p{page}")


# ---- content pages -----------------------------------------------------------------------------------

def job_description(slug):
    return webpage(f"job-description/{quote(slug)}", label=f"job description {slug}")


def sitemap():
    return webpage("sitemap", label="sitemap")


def salary_page(title, location):
    """The salary page HTML (CutshortNotFound when the site redirects a role
    it has no page for)."""
    return html_get(f"/salary/{quote(title)}/{quote(location)}", label=f"salary {title} in {location}",
                    allow_redirect_as_missing=True)


def analytics(context, params):
    body = api_get(f"/api/get-analytics-data/{quote(context)}", params, label=f"analytics {context}")
    return body.get("data") if isinstance(body, dict) else None


# ---- Algolia -----------------------------------------------------------------------------------------

def algolia(index, query, hits=10):
    """The search box's suggestions from one Algolia index -> its hits."""
    url = f"https://{refdata.ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{quote(index)}/query"
    label = f"algolia {index} {query!r}"
    headers = {"x-algolia-api-key": refdata.ALGOLIA_SEARCH_KEY, "x-algolia-application-id": refdata.ALGOLIA_APP_ID,
               "content-type": "application/json", "referer": f"{refdata.BASE_URL}/", "origin": refdata.BASE_URL}
    payload = json.dumps({"params": urlencode({"query": query, "hitsPerPage": hits})})

    def send(sess):
        resp = sess.post(url, headers=headers, data=payload, timeout=TIMEOUT)
        body = _classify(resp, label)
        if not isinstance(body, dict) or not isinstance(body.get("hits"), list):
            raise CutshortUpstreamError(f"unexpected payload on {label}")
        return body["hits"]
    return _attempts(label, send)


# ---- memo / cache / parallel ---------------------------------------------------------------------------

_memo = OrderedDict()
_memo_lock = threading.Lock()
MEMO_TTL = 600
MEMO_MAX = 256


def memoized(key, fn, ttl=MEMO_TTL):
    now = time.monotonic()
    with _memo_lock:
        hit = _memo.get(key)
        if hit and now - hit[0] < ttl:
            _memo.move_to_end(key)
            return hit[1]
    value = fn()
    with _memo_lock:
        _memo[key] = (now, value)
        _memo.move_to_end(key)
        while len(_memo) > MEMO_MAX:
            _memo.popitem(last=False)
    return value


def shared_raw(name, params, build, ttl):
    """An upstream payload shared by several routes: in-process memo, then
    the service's response cache (pods share it) when one is installed,
    then build(). Without a `cache` module (the standalone package) it is
    the in-process memo alone."""
    try:
        from cache import cached_call
    except ImportError:
        cached_call = None
    seconds = ttl.total_seconds() if hasattr(ttl, "total_seconds") else ttl
    key = (name, json.dumps(params, sort_keys=True))
    if cached_call is None:
        return memoized(key, build, ttl=min(seconds, MEMO_TTL))
    return memoized(key, lambda: cached_call(f"cutshort.raw.{name}", params, lambda **_: build(), ttl),
                    ttl=min(seconds, MEMO_TTL))


def run_parallel(fns, workers):
    """Run zero-arg callables in parallel; results align with `fns`. Each
    result is ("ok", value) or ("error", exception)."""
    def guard(fn):
        try:
            return ("ok", fn())
        except Exception as e:
            return ("error", e)
    if not fns:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(fns)))) as ex:
        return list(ex.map(guard, fns))


if __name__ == "__main__":
    # Smoke test: python cutshort/fetch.py
    data = listing("python-jobs-in-pune")
    print("listing:", data["pageData"]["liveJobCount"], [j["headline"] for j in data["pageData"]["jobs"][:3]])
    ref = data["pageData"]["jobs"][0]["publicUrl"].rsplit("-", 1)[-1]
    detail = job(ref)
    print("job:", detail["pageData"]["headline"], detail["pageData"]["salaryRange"])
    comp = company(data["pageData"]["jobs"][0]["companyId"]["alias"])
    print("company:", comp["pageData"]["company"]["name"], comp["pageData"]["company"].get("totalJobsOfCompany"))
    print("algolia:", [h.get("name") for h in algolia("prod_skills", "react", 3)])
