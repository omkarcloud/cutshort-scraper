"""/cutshort/salaries/* — the site's salary pages (/salary/<role>/<city>):
the top 5 / 10 / 20 percent figures, the trend across cities and across
roles, FAQs and related pages, read off the page's __NEXT_DATA__ (no JSON
route exists for them); plus the list of roles and locations with a page."""
from cutshort import fetch, refdata
from cutshort import parsers as P


def details(title, location=None):
    """The salary page of `title` (a role slug / name / link) in `location`
    (india, remote or one of the 14 cities; a link's city when omitted, else
    india)."""
    slug = title["title"]
    loc = location or title.get("location") or "india"
    html = fetch.salary_page(slug, loc)
    out = P.salary_page(html, slug, loc)
    if out is None or not out.get("percentiles", {}).get("top_10_percent"):
        raise fetch.CutshortNotFound(f"Cutshort has no salary page for {slug!r} in {loc!r}; see /cutshort/salaries/titles")
    return out


def titles(location=None):
    """Every role the site reports salaries for (37) and the 16 locations
    each has a page in; with `location`, the pages of that location."""
    pages = refdata.salary_pages()
    titles_map = refdata.salary_titles()
    roles = []
    for slug, label in sorted(titles_map.items(), key=lambda kv: kv[1]):
        locations = sorted({loc for (t, loc) in pages if t == slug})
        if location is not None and location not in locations:
            continue
        roles.append({"slug": slug, "title": label,
                      "link": f"{refdata.BASE_URL}/salary/{slug}/{location or 'india'}",
                      "locations": locations if location is None else [location]})
    return {"titles": roles, "count": len(roles),
            "locations": [{"slug": slug, "name": name, "site_name": site_name}
                          for slug, (name, site_name) in refdata.SALARY_LOCATIONS.items()]}
