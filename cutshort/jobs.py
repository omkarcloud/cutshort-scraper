"""/cutshort/jobs/* — job search (a listing page resolved from free text /
city / remote), job details, batch lookup, similar jobs and the listing
catalogue, from the site's own backend JSON."""
import re
from datetime import datetime, timedelta, timezone

from cutshort import cache_config as ttl
from cutshort import fetch, refdata
from cutshort import parsers as P
from cutshort.shared import compact, slugify


def _workers():
    try:
        import config
        return int(config.CUTSHORT_WORKERS)
    except Exception:
        return 4


# ---- the catalogue (live, else the snapshot) -------------------------------------------------------------

def live_catalogue():
    """The listing catalogue from the site's sitemap (daily cache), the
    packaged snapshot when the site does not answer -> (catalogue, source)."""
    def build():
        return P.sitemap_catalogue(fetch.sitemap())
    try:
        rows = fetch.shared_raw("sitemap", {}, build, ttl.SITEMAP_RAW_CACHE)
        if len(rows.get("jobs") or []) > 1000:
            return refdata.catalogue(rows["jobs"]), rows, "site"
    except (fetch.CutshortUpstreamError, fetch.CutshortNotFound, fetch.CutshortBadRequest) as e:
        print(f"cutshort: live sitemap skipped: {e}")
    return refdata.catalogue(), refdata.snapshot(), "snapshot"


# ---- resolving free text to a listing topic ----------------------------------------------------------------

_STRIP_SUFFIXES = ("-developer", "-developers", "-engineer", "-engineers", "-engineering", "-jobs", "-job",
                   "-role", "-roles", "-position", "-positions", "-programmer", "-programming", "-specialist")
_STRIP_PREFIXES = ("senior-", "sr-", "junior-", "jr-", "lead-", "principal-", "staff-")


def _candidates(text):
    """Slug forms of a free-text query, most literal first."""
    slug = slugify(text)
    if not slug:
        return []
    out = [slug, compact(text)]
    base = slug
    for prefix in _STRIP_PREFIXES:
        if base.startswith(prefix) and len(base) > len(prefix):
            base = base[len(prefix):]
            out.append(base)
            break
    for suffix in _STRIP_SUFFIXES:
        if base.endswith(suffix) and len(base) > len(suffix):
            out.append(base[: -len(suffix)])
            out.append(compact(base[: -len(suffix)]))
    return [c for i, c in enumerate(out) if c and c not in out[:i]]


def _fuzzy(cat, text):
    """Topics whose slug tokens cover every query token, best first."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]
    if not tokens:
        return []
    hits = []
    for topic in cat.topics:
        parts = topic.split("-")
        joined = topic.replace("-", "")
        if all(t in parts or (len(t) > 2 and t in joined) for t in tokens):
            hits.append(topic)
    hits.sort(key=lambda t: (-cat.weight(t), len(t), t))
    return hits


def resolve_topic(text, cat=None):
    """Free text -> (topic slug, how it matched) or (None, None). Exact slug
    forms first, then the site's own skill / title suggestions, then a
    token match over the catalogue."""
    cat = cat or refdata.catalogue()
    for cand in _candidates(text):
        if cand in cat.topics:
            return cand, "exact"
        for topic in cat.by_compact(cand):
            return topic, "exact"
    try:
        hits = fetch.algolia(refdata.ALGOLIA_INDICES["skills"], text, 5)
    except (fetch.CutshortUpstreamError, fetch.CutshortNotFound, fetch.CutshortBadRequest) as e:
        print(f"cutshort: skill suggestions for {text!r} skipped: {e}")
        hits = []
    for hit in hits:
        for name in [hit.get("name"), *(hit.get("alias") or [])]:
            for cand in _candidates(name or ""):
                if cand in cat.topics:
                    return cand, "skill"
                for topic in cat.by_compact(cand):
                    return topic, "skill"
    fuzzy = _fuzzy(cat, text)
    if fuzzy:
        return fuzzy[0], "fuzzy"
    return None, None


def resolve_listing(query=None, location=None, remote=None):
    """The public search params -> the listing slug to fetch + how the
    query was read. A slug / link in `query` is parsed and `location` /
    `remote` override its parts; free text resolves to a topic."""
    cat, _rows, _source = live_catalogue()
    topic, city, is_remote, matched = None, None, False, None
    if query and query.get("slug"):
        topic, city, is_remote = refdata.parse_listing_slug(query["slug"])
        matched = "slug"
    elif query and query.get("text"):
        topic, matched = resolve_topic(query["text"], cat)
        if topic is None:
            raise fetch.CutshortNotFound(
                f"Cutshort has no job listing for {query['text']!r}; try a skill or role name "
                f"(python, react.js, product manager) or pick a slug from /cutshort/jobs/categories?query=…")
    if location is not None:
        city = location
    if remote is not None:
        is_remote = bool(remote)
    if topic is None:
        topic, matched = refdata.ALL_JOBS_TOPIC, "all"
    if is_remote and topic == refdata.ALL_JOBS_TOPIC and not city:
        slug = "remote-jobs" if cat.has("remote-jobs") else refdata.build_listing_slug(topic, None, True)
    else:
        slug = refdata.build_listing_slug(topic, city, is_remote)
    return {"slug": slug, "topic": topic, "topic_title": cat.topic_label(topic), "city": city,
            "is_remote": is_remote, "matched": matched, "known": cat.has(slug), "catalogue": cat}


def _variants(cat, topic):
    entry = cat.topics.get(topic) or {}
    out = [refdata.build_listing_slug(topic)]
    out += [refdata.build_listing_slug(topic, c) for c in sorted(entry.get("cities", ()))]
    if entry.get("remote"):
        out.append(refdata.build_listing_slug(topic, None, True))
    out += [refdata.build_listing_slug(topic, c, True) for c in sorted(entry.get("remote_cities", ()))]
    return [s for s in out if cat.has(s)]


# ---- client-side filters -------------------------------------------------------------------------------------

def _matches(job, experience_years=None, min_salary_lakhs=None, max_salary_lakhs=None, role_type=None,
             company_type=None, remote_policy=None, posted_within_days=None, skill=None, now=None):
    if experience_years is not None:
        band = job.get("experience") or {}
        low, high = band.get("min_years"), band.get("max_years")
        if (low is not None and experience_years < low) or (high is not None and experience_years > high):
            return False
    salary = job.get("salary") or {}
    if min_salary_lakhs is not None:
        top = salary.get("max_lakhs")
        if salary.get("currency") != "INR" or top is None or top < min_salary_lakhs:
            return False
    if max_salary_lakhs is not None:
        bottom = salary.get("min_lakhs")
        if salary.get("currency") != "INR" or (bottom is not None and bottom > max_salary_lakhs):
            return False
    if role_type and role_type not in (job.get("role_types") or []):
        return False
    if company_type:
        kind = ((job.get("company") or {}).get("type") or "").lower()
        if company_type == "product" and "product" not in kind:
            return False
        if company_type == "services" and "service" not in kind:
            return False
        if company_type == "agency" and "agency" not in kind:
            return False
    if remote_policy and job.get("remote_policy") != remote_policy:
        return False
    if posted_within_days is not None:
        posted = job.get("posted_on")
        if not posted:
            return False
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=posted_within_days)
        if datetime.strptime(posted, "%Y-%m-%d").replace(tzinfo=timezone.utc) < cutoff:
            return False
    if skill:
        names = {compact(s.get("name")) for s in job.get("skills") or []}
        codes = {s.get("code") for s in job.get("skills") or []}
        if not all(compact(s) in names or s in codes for s in skill):
            return False
    return True


# ---- endpoints -----------------------------------------------------------------------------------------------------

def search(query=None, location=None, remote=None, page=1, experience_years=None, min_salary_lakhs=None,
           max_salary_lakhs=None, role_type=None, company_type=None, remote_policy=None, posted_within_days=None,
           skill=None):
    """One page (50 cards, newest first) of the Cutshort listing that
    matches `query` (a skill / role / topic, or a listing slug or link),
    `location` (one of the site's 14 cities) and `remote`. Each card
    carries the full description, salary and experience bands, skills and
    the company card. The other filters apply to the page's cards (the
    site has no server-side experience / salary / type filters), so a
    filtered page can carry fewer than 50 jobs."""
    resolved = resolve_listing(query, location, remote)
    slug = resolved["slug"]
    try:
        raw = fetch.listing(slug, page)
    except fetch.PastEnd:
        raw = None
    except fetch.CutshortNotFound:
        variants = _variants(resolved["catalogue"], resolved["topic"])
        hint = f" Listings for this topic: {', '.join(variants[:12])}." if variants else ""
        raise fetch.CutshortNotFound(f"Cutshort has no '{slug}' listing (topic {resolved['topic']!r}"
                                     + (f" in {resolved['city']}" if resolved["city"] else "")
                                     + (", remote" if resolved["is_remote"] else "") + f").{hint}")
    if raw is None:
        result = {"listing": {"slug": slug, "link": f"{refdata.BASE_URL}/jobs/{slug}", "title": None, "description": None},
                  "jobs": [], "related_listings": [],
                  "pagination": {"page": page, "items_per_page": refdata.PAGE_SIZE, "total_pages": page - 1, "total_count": None}}
    else:
        result = P.listing_page(raw, slug, page)
    filters = {"experience_years": experience_years, "min_salary_lakhs": min_salary_lakhs,
               "max_salary_lakhs": max_salary_lakhs, "role_type": role_type, "company_type": company_type,
               "remote_policy": remote_policy, "posted_within_days": posted_within_days, "skill": skill}
    if any(v is not None for v in filters.values()):
        result["jobs"] = [j for j in result["jobs"] if _matches(j, **filters)]
    result["listing"].update({"topic": resolved["topic"], "topic_title": resolved["topic_title"],
                              "location": refdata.CITIES.get(resolved["city"], (None,))[0] if resolved["city"] else None,
                              "location_slug": resolved["city"], "is_remote": resolved["is_remote"],
                              "query_matched_by": resolved["matched"]})
    result["filters"] = {k: v for k, v in filters.items()}
    result["jobs_on_page"] = len(result["jobs"])
    return result


def _detail(ref, include_similar=False):
    raw = fetch.job(ref)
    similar = None
    if include_similar:
        record_id = (raw.get("pageData") or {}).get("_id")
        if record_id:
            try:
                similar = fetch.similar_jobs(record_id)
            except (fetch.CutshortUpstreamError, fetch.CutshortNotFound, fetch.CutshortBadRequest) as e:
                print(f"cutshort: similar jobs of {ref} skipped: {e}")
    return P.job_details(raw, similar)


def details(job, include_similar=False):
    """The full job: description, salary and experience bands, skills with
    codes, remote policy, posting date, category tags, recruiter, the
    company profile card, and (include_similar) the ten jobs the site lists
    next to it. 404 when the site has no such job."""
    return _detail(job, include_similar)


def batch(jobs, include_similar=False):
    """Up to MAX_BATCH jobs by id / slug / link, fetched in parallel. Jobs
    the site does not have are listed under `errors` instead of failing the call."""
    outcomes = fetch.run_parallel([lambda j=j: _detail(j, include_similar) for j in jobs], _workers())
    out, errors = [], {}
    for ref, (status, value) in zip(jobs, outcomes):
        if status == "ok":
            out.append(value)
        elif isinstance(value, fetch.CutshortNotFound):
            errors[str(ref)] = "not found"
        else:
            raise value
    return {"jobs": out, "count": len(out), "errors": errors or None}


def similar(job):
    """The ten jobs the site lists as similar to `job`."""
    raw = fetch.job(job)
    page = raw.get("pageData") or {}
    record_id = page.get("_id")
    rows = fetch.similar_jobs(record_id) if record_id else []
    jobs = [P.job_card(r) for r in rows if isinstance(r, dict)]
    return {"job": {"id": P.job_details(raw).get("id"), "record_id": record_id, "title": page.get("headline"),
                    "link": page.get("publicUrl")},
            "jobs": jobs, "count": len(jobs)}


def categories(query=None, location=None, remote=None, page=1):
    """The listing catalogue (every `<topic>-jobs[-in-<city>]` page the site
    has, with its title), filtered by `query` (topic text), `location` and
    `remote`, 50 a page. The slugs are what /cutshort/jobs/search takes as `query`."""
    cat, rows, source = live_catalogue()
    text = ((query or {}).get("text") or "") if isinstance(query, dict) else ""
    tokens = [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]
    wanted_slug = (query or {}).get("slug") if isinstance(query, dict) else None
    entries = []
    for slug, label in rows.get("jobs") or []:
        parsed = refdata.parse_listing_slug(slug)
        if not parsed:
            continue
        topic, city, is_remote = parsed
        if wanted_slug and slug != wanted_slug:
            continue
        if location is not None and city != location:
            continue
        if remote is not None and bool(remote) != is_remote:
            continue
        if tokens:
            parts = topic.split("-")
            joined = topic.replace("-", "")
            if not all(t in parts or (len(t) > 2 and t in joined) for t in tokens):
                continue
        entries.append((slug, label, topic, city, is_remote))
    entries.sort(key=lambda e: (-cat.weight(e[2]), e[2], e[4], e[3] or ""))
    total = len(entries)
    size = refdata.CATEGORIES_PAGE_SIZE
    chunk = entries[(page - 1) * size: page * size]
    return {
        "source": source,
        "categories": [{"slug": slug, "title": label, "link": f"{refdata.BASE_URL}/jobs/{slug}", "topic": topic,
                        "topic_title": cat.topic_label(topic),
                        "location": refdata.CITIES.get(city, (None,))[0] if city else None, "location_slug": city,
                        "is_remote": is_remote} for slug, label, topic, city, is_remote in chunk],
        "pagination": {"page": page, "items_per_page": size, "total_pages": ceil_div(total, size), "total_count": total},
    }


def ceil_div(a, b):
    return -(-a // b) if a else 0
