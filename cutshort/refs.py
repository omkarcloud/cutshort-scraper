"""Cutshort input parsing: ONE param per input that auto-detects its forms
(tripadvisor QueryOrLinkField convention, never a sibling `url`/`id` pair).
Every resolver returns plain JSON values so validated params stay usable as
a response-cache key, and raises ValueError with a user-facing message.

  job       I1i8FXO2 | 6abe4d08f4afa2722c7a7b28 | Full-Stack-Software-Engineer-Provenir-I1i8FXO2
            | https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2   -> "I1i8FXO2"
            (the 8-char id at the end of every job slug, or the 24-hex record id — the
             backend resolves both)
  company   meesho-Xf1Xrsdc | https://cutshort.io/company/meesho-Xf1Xrsdc | Meesho (a name,
            looked up through the site's search box at call time)
                                        -> {"alias": "meesho-Xf1Xrsdc", "name": None}
                                         | {"alias": None, "name": "Meesho"}
  query     python | React.js | Python Developer (free text, resolved to a listing topic
            at call time) | python-jobs-in-pune | https://cutshort.io/jobs/remote-python-jobs
            (a listing slug / link, used as is)
                                        -> {"text": "python", "slug": None}
                                         | {"text": None, "slug": "python-jobs-in-pune"}
  location  Pune | bengaluru | Bangalore (Bengaluru) | delhi ncr | gurgaon  -> "pune" / "bangalore-bengaluru" / …
            (the 14 job listing cities, matched on slug, name and alternate spellings)
  category  (company directory) fintech | startups | https://cutshort.io/companies/fintech-companies-in-pune
                                        -> "fintech" / "startups" / "fintech-companies-in-pune"
  title     (salary pages) python-developer | Python Developer | https://cutshort.io/salary/python-developer/pune
                                        -> {"title": "python-developer", "location": None | "pune"}
  salary_location  bangalore | Bengaluru | india | remote                    -> "bangalore" / "india" / "remote"
"""
import re
from urllib.parse import unquote, urlparse

from cutshort import refdata
from cutshort.shared import compact, slugify

_HOST_RE = re.compile(r"(?:^|\.)cutshort\.(?:io|ai)$")
_SLUG_BAD = re.compile(r"[/?#\\<>\"]")


def _parse_url(value):
    """-> (host, path) when value looks like a Cutshort URL or host path,
    None when it is plain text. Raises ValueError for another site."""
    raw = (value or "").strip()
    low = raw.lower()
    if low.startswith("//"):
        raw = "https:" + raw
    elif not low.startswith(("http://", "https://")):
        head = low.split("/", 1)[0]
        if not _HOST_RE.search(head):
            return None
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if not _HOST_RE.search(host):
        raise ValueError("Must be a cutshort.io link.")
    return host, unquote(parsed.path)


def _split(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


# ---- jobs -------------------------------------------------------------------------------------------

JOB_HINT = ("Must be a Cutshort job: its link (https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2), "
            "its slug, or the 8-character id that ends the slug (I1i8FXO2).")


def resolve_job(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(JOB_HINT)
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(JOB_HINT)
    if url:
        match = re.search(r"/(?:job|view/j|vj)/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be job pages (https://cutshort.io/job/<slug>).")
        raw = match.group(1)
    if _SLUG_BAD.search(raw) or " " in raw:
        raise ValueError(JOB_HINT)
    if re.fullmatch(r"[0-9a-f]{24}", raw):
        return raw                                       # the record id
    match = re.search(r"([A-Za-z0-9_]{8})$", raw)
    if match and (len(raw) == 8 or raw[-9] == "-"):
        return match.group(1)
    raise ValueError(JOB_HINT)


def resolve_jobs(value, limit=refdata.MAX_BATCH):
    """'I1i8FXO2, https://cutshort.io/job/…-p7PgIKOo' -> ['I1i8FXO2', 'p7PgIKOo'] (deduped, 1..limit)."""
    out = []
    for item in _split(value):
        job_id = resolve_job(item)
        if job_id not in out:
            out.append(job_id)
    if not out:
        raise ValueError("Must list at least one job id, slug or link (comma-separated).")
    if len(out) > limit:
        raise ValueError(f"At most {limit} jobs.")
    return out


# ---- companies ----------------------------------------------------------------------------------------

COMPANY_HINT = ("Must be a company page link or alias (https://cutshort.io/company/meesho-Xf1Xrsdc, "
                "meesho-Xf1Xrsdc) or a company name (Meesho).")
# the site slugs any punctuation into aliases (b+m-surface-systems--22-mf5FmoLl,
# jobs-at-[object-object]-86-Ork9DhOG): a lowercase prefix ending in -<8-char id>
_ALIAS_RE = re.compile(r"^[a-z0-9][^\sA-Z/?#\\<>\"]*-[A-Za-z0-9_]{8}$")


def resolve_company(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(COMPANY_HINT)
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(COMPANY_HINT)
    if url:
        match = re.search(r"/(?:company|view/c|vc)/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be company pages (https://cutshort.io/company/<alias>).")
        return {"alias": match.group(1), "name": None}
    if _ALIAS_RE.match(raw) and " " not in raw:
        return {"alias": raw, "name": None}
    name = " ".join(raw.split())
    if _SLUG_BAD.search(name) or len(name) > 150:
        raise ValueError(COMPANY_HINT)
    return {"alias": None, "name": name}


# ---- listings (job search) -------------------------------------------------------------------------------

QUERY_HINT = ("Must be a skill, role or topic (python, React.js, product manager), a Cutshort listing slug "
              "(python-jobs-in-pune) or a listing link (https://cutshort.io/jobs/remote-python-jobs).")


def resolve_query(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(QUERY_HINT)
    if url:
        match = re.search(r"/jobs/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be job listing pages (https://cutshort.io/jobs/<slug>).")
        slug = match.group(1).lower()
        if not refdata.parse_listing_slug(slug):
            raise ValueError(QUERY_HINT)
        return {"text": None, "slug": slug}
    if len(raw) > 150 or _SLUG_BAD.search(raw):
        raise ValueError(QUERY_HINT)
    low = raw.lower()
    if " " not in low and refdata.parse_listing_slug(low) and refdata.catalogue().has(low):
        return {"text": None, "slug": low}
    return {"text": " ".join(raw.split()), "slug": None}


# ---- locations ----------------------------------------------------------------------------------------------

def _city_index():
    index = {}
    for slug, (name, alternates) in refdata.CITIES.items():
        for key in [slug, name, *alternates, slug.replace("-", " ")]:
            index.setdefault(" ".join(key.lower().split()), slug)
        index.setdefault(compact(name), slug)
    return index


_CITY_INDEX = None
LOCATION_HINT = "Must be one of the cities Cutshort lists jobs by (Bangalore, Mumbai, Delhi NCR, Pune, …); see /cutshort/locations."


def resolve_location(value):
    global _CITY_INDEX
    if _CITY_INDEX is None:
        _CITY_INDEX = _city_index()
    raw = " ".join((value or "").lower().split())
    if not raw:
        return None
    if raw in ("india", "all", "anywhere"):
        return None
    hit = _CITY_INDEX.get(raw) or _CITY_INDEX.get(compact(raw) or "") or _CITY_INDEX.get(raw.replace("-", " "))
    if hit is None:
        for token in re.split(r"[\s,/()]+", raw):
            if token and token in _CITY_INDEX:
                hit = _CITY_INDEX[token]
                break
    if hit is None:
        raise ValueError(f"'{value}' is not a city Cutshort lists jobs by. " + LOCATION_HINT)
    return hit


# ---- company directories ----------------------------------------------------------------------------------

CATEGORY_HINT = ("Must be a company directory category (fintech, saas, startups, e-learning, …), a directory slug "
                 "(fintech-companies-in-pune) or its link (https://cutshort.io/companies/fintech); "
                 "see /cutshort/companies/categories.")


def resolve_category(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(CATEGORY_HINT)
    if url:
        match = re.search(r"/companies/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be company directory pages (https://cutshort.io/companies/<slug>).")
        return match.group(1).lower()
    slug = slugify(raw)
    if not slug or len(slug) > 100:
        raise ValueError(CATEGORY_HINT)
    return slug


# ---- salaries -----------------------------------------------------------------------------------------------

TITLE_HINT = ("Must be a role Cutshort has a salary page for (python-developer, Python Developer, "
              "data-scientist, …) or its link (https://cutshort.io/salary/python-developer/bangalore); "
              "see /cutshort/salaries/titles.")


def resolve_salary_title(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(TITLE_HINT)
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(TITLE_HINT)
    if url:
        match = re.search(r"/salary/([^/?#]+)(?:/([^/?#]+))?", url[1])
        if not match:
            raise ValueError("Links must be salary pages (https://cutshort.io/salary/<role>/<city>).")
        title, location = match.group(1).lower(), (match.group(2) or "").lower() or None
        return {"title": title, "location": resolve_salary_location(location) if location else None}
    slug = slugify(raw)
    if not slug or len(slug) > 100:
        raise ValueError(TITLE_HINT)
    titles = refdata.salary_titles()
    if slug in titles:
        return {"title": slug, "location": None}
    wanted = compact(raw)
    for known, label in titles.items():
        if compact(label) == wanted or compact(known) == wanted:
            return {"title": known, "location": None}
    for suffix in ("-jobs", "-job", "-salary", "-salaries"):
        if slug.endswith(suffix) and slug[: -len(suffix)] in titles:
            return {"title": slug[: -len(suffix)], "location": None}
    raise ValueError(f"'{value}' has no salary page on Cutshort. " + TITLE_HINT)


def _salary_location_index():
    index = {}
    for slug, (name, site_name) in refdata.SALARY_LOCATIONS.items():
        for key in [slug, name, site_name, slug.replace("-", " ")]:
            index.setdefault(" ".join(key.lower().split()), slug)
        index.setdefault(compact(name), slug)
    for city, (name, alternates) in refdata.CITIES.items():
        target = refdata.CITY_TO_SALARY_LOCATION.get(city, city)
        if target in refdata.SALARY_LOCATIONS:
            for key in [city, name, *alternates]:
                index.setdefault(" ".join(key.lower().split()), target)
    for key in ("wfh", "work from home", "anywhere"):
        index.setdefault(key, "remote")
    index.setdefault("all", "india")
    return index


_SALARY_LOCATION_INDEX = None
SALARY_LOCATION_HINT = "Must be india, remote or one of the 14 cities Cutshort reports salaries for; see /cutshort/locations."


def resolve_salary_location(value):
    global _SALARY_LOCATION_INDEX
    if _SALARY_LOCATION_INDEX is None:
        _SALARY_LOCATION_INDEX = _salary_location_index()
    raw = " ".join((value or "").lower().split())
    if not raw:
        return None
    hit = _SALARY_LOCATION_INDEX.get(raw) or _SALARY_LOCATION_INDEX.get(compact(raw) or "")
    if hit is None:
        for token in re.split(r"[\s,/()|]+", raw):
            if token and token in _SALARY_LOCATION_INDEX:
                hit = _SALARY_LOCATION_INDEX[token]
                break
    if hit is None:
        raise ValueError(f"'{value}' is not a salary location Cutshort knows. " + SALARY_LOCATION_HINT)
    return hit


# ---- job descriptions ---------------------------------------------------------------------------------------

JD_HINT = ("Must be a role Cutshort has a job description template for (python-developer, Backend Developer, …) "
           "or its link (https://cutshort.io/job-description/python-developer); see /cutshort/job-descriptions.")


def resolve_job_description(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(JD_HINT)
    try:
        url = _parse_url(raw)
    except ValueError:
        raise ValueError(JD_HINT)
    if url:
        match = re.search(r"/job-description/([^/?#]+)", url[1])
        if not match:
            raise ValueError("Links must be job description pages (https://cutshort.io/job-description/<role>).")
        return match.group(1).lower()
    slug = slugify(raw)
    if not slug or len(slug) > 100:
        raise ValueError(JD_HINT)
    known = refdata.job_description_slugs()
    if slug in known:
        return slug
    wanted = compact(raw)
    for item in known:
        if compact(item) == wanted:
            return item
    for suffix in ("-jobs", "-job", "-job-description"):
        if slug.endswith(suffix) and slug[: -len(suffix)] in known:
            return slug[: -len(suffix)]
    return slug          # the site decides (config_not_found -> 404)
