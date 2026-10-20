"""/cutshort/companies/* — company pages (profile, hiring team, FAQs, tech
stack, socials, open jobs, similar companies), a company's open jobs, the
company directories (fintech, saas, startups in Pune, …) and the company
name search.

A `company` param arrives resolved by refs.resolve_company: a page alias
(`meesho-Xf1Xrsdc`, from any company link) or a name that is looked up
through the site's own search box (exact match first, else the first hit)."""
from cutshort import cache_config as ttl
from cutshort import fetch, refdata
from cutshort import parsers as P
import re

from cutshort.shared import compact


# ---- resolving --------------------------------------------------------------------------------------------

def search(query, limit=10):
    """Companies whose name matches `query` (the site's search box)."""
    rows = fetch.algolia(refdata.ALGOLIA_INDICES["companies"], query, min(limit, 50))
    companies = [P.company_suggestion(r) for r in rows if isinstance(r, dict)][:limit]
    return {"query": query, "companies": companies, "count": len(companies)}


def resolve_alias(company):
    """A resolved `company` ref -> its page alias (a name is looked up on
    the site; memoised + cached)."""
    if company.get("alias"):
        return company["alias"]
    name = company["name"]

    def build():
        hits = [P.company_suggestion(r) for r in fetch.algolia(refdata.ALGOLIA_INDICES["companies"], name, 10)
                if isinstance(r, dict)]
        wanted = compact(name)
        exact = [c for c in hits if compact(c.get("name")) == wanted and c.get("alias")]
        hit = (exact or [c for c in hits if c.get("alias")] or [None])[0]
        if not hit:
            raise fetch.CutshortNotFound(f"Cutshort has no company named {name!r}")
        return hit["alias"]
    return fetch.shared_raw("company_alias_by_name", {"name": name.lower()}, build, ttl.COMPANY_ALIAS_CACHE)


# ---- endpoints ----------------------------------------------------------------------------------------------

def details(company, page=1):
    """The company page: identity, type / size / stage / funding, founding
    year, domains, followers, description, website and socials, FAQs, tech
    stack, team and hiring team, photos, ten open jobs a page (`page`) with
    the job count, and the similar companies the site lists."""
    alias = resolve_alias(company)
    raw = fetch.company(alias, page)
    out = P.company_profile(raw, alias)
    if not out.get("name"):
        raise fetch.CutshortNotFound(f"Cutshort has no company page for {alias!r}")
    return out


def open_jobs(company, page=1):
    """One page (10) of a company's open jobs, newest first, with the
    company card."""
    alias = resolve_alias(company)
    raw = fetch.company(alias, page)
    profile = P.company_profile(raw, alias)
    if not profile.get("name"):
        raise fetch.CutshortNotFound(f"Cutshort has no company page for {alias!r}")
    jobs = profile.pop("jobs")
    pagination = profile.pop("jobs_pagination")
    pagination["page"] = page
    keys = ("id", "name", "alias", "link", "logo", "type", "size", "stage", "funding", "founded_year",
            "followers_count", "jobs_count", "is_hiring_for_client")
    return {"company": {k: profile.get(k) for k in keys}, "jobs": jobs, "pagination": pagination}


def _city_tokens(location):
    """The tokens a directory slug may carry for a city ('bangalore-bengaluru'
    -> ['bangalore-bengaluru', 'bengaluru', 'bangalore', 'blr'])."""
    name, alternates = refdata.CITIES.get(location, (None, ()))
    tokens = [location, *location.split("-")[::-1], *alternates]
    return [t for i, t in enumerate(tokens) if t and t not in tokens[:i]]


def _city_of_directory(slug):
    match = re.search(r"-in-([a-z-]+)$", slug)
    if not match:
        return None
    token = match.group(1)
    for city in refdata.CITIES:
        if token in _city_tokens(city):
            return city
    return None


def directory_slug(category, location, labels):
    """The directory slug for a category in a city, as the site names it
    (`<category>-companies-in-<city>`, `startups-in-<city>`); None when
    the site has no such page."""
    for token in _city_tokens(location):
        for cand in (f"{category}-companies-in-{token}", f"{category}-in-{token}", f"{category}-{token}"):
            if cand in labels:
                return cand
    return None


def directory(category=None, location=None, page=1):
    """One page (50) of a company directory: `category` a directory slug
    (fintech, saas, startups, e-learning, consulting-professional-services,
    or a full slug / link) and `location` one of the 14 cities. With no
    category the startups directory."""
    labels = refdata.company_listing_labels()
    try:
        rows = fetch.shared_raw("sitemap", {}, lambda: P.sitemap_catalogue(fetch.sitemap()), ttl.SITEMAP_RAW_CACHE)
        if len(rows.get("companies") or []) > 100:
            labels = dict(rows["companies"])
    except (fetch.CutshortUpstreamError, fetch.CutshortNotFound, fetch.CutshortBadRequest) as e:
        print(f"cutshort: live sitemap skipped: {e}")
    slug = category or "startups"
    if location and "-in-" not in slug:
        resolved = directory_slug(slug, location, labels)
        if resolved is None:
            cities = sorted({_city_of_directory(s) for s in labels if s.startswith(slug + "-") and _city_of_directory(s)} - {None})
            raise fetch.CutshortNotFound(
                f"Cutshort has no '{slug}' company directory for {refdata.CITIES.get(location, (location,))[0]}."
                + (f" Cities with one: {', '.join(cities)}." if cities else " It exists only countrywide.")
                + " See /cutshort/companies/categories.")
        slug = resolved
    elif location and _city_of_directory(slug) != location:
        raise fetch.CutshortNotFound(f"'{slug}' is a directory for another city; drop `location` or pass a category.")
    try:
        raw = fetch.directory(slug, page)
    except fetch.PastEnd:
        return {"directory": {"slug": slug, "link": f"{refdata.BASE_URL}/companies/{slug}", "title": labels.get(slug),
                              "description": None, "category": slug.split("-companies-in-")[0].split("-in-")[0],
                              "location": refdata.CITIES.get(location, (None,))[0] if location else None,
                              "location_slug": location},
                "companies": [], "related_directories": [],
                "pagination": {"page": page, "items_per_page": refdata.DIRECTORY_PAGE_SIZE, "total_pages": page - 1,
                               "total_count": None}}
    except fetch.CutshortNotFound:
        head = (category or "startups").split("-companies-in-")[0].split("-in-")[0]
        similar = [s for s in labels if head in s][:10]
        raise fetch.CutshortNotFound(f"Cutshort has no company directory '{slug}'."
                                     + (f" Directories like it: {', '.join(similar)}." if similar else "")
                                     + " See /cutshort/companies/categories.")
    result = P.directory_page(raw, slug, page)
    if not result["directory"].get("title"):
        result["directory"]["title"] = labels.get(slug)
    full = len(result["companies"]) >= refdata.DIRECTORY_PAGE_SIZE
    result["pagination"]["total_pages"] = page + 1 if full else page
    city = location or _city_of_directory(slug)
    result["directory"]["category"] = slug.split("-companies-in-")[0].split("-in-")[0]
    result["directory"]["location"] = refdata.CITIES.get(city, (None,))[0] if city else None
    result["directory"]["location_slug"] = city
    return result


def categories(location=None):
    """Every company directory the site has (563 pages: a category, or a
    category in one of the cities), with its title."""
    labels = refdata.company_listing_labels()
    try:
        rows = fetch.shared_raw("sitemap", {}, lambda: P.sitemap_catalogue(fetch.sitemap()), ttl.SITEMAP_RAW_CACHE)
        if len(rows.get("companies") or []) > 100:
            labels = dict(rows["companies"])
            source = "site"
        else:
            source = "snapshot"
    except (fetch.CutshortUpstreamError, fetch.CutshortNotFound, fetch.CutshortBadRequest) as e:
        print(f"cutshort: live sitemap skipped: {e}")
        source = "snapshot"
    out = []
    for slug, label in sorted(labels.items()):
        city = _city_of_directory(slug)
        if location is not None and city != location:
            continue
        head = slug.split("-companies-in-")[0].split("-in-")[0]
        out.append({"slug": slug, "title": label, "link": f"{refdata.BASE_URL}/companies/{slug}", "category": head,
                    "location": refdata.CITIES.get(city, (None,))[0] if city else None, "location_slug": city})
    return {"source": source, "directories": out, "count": len(out)}
