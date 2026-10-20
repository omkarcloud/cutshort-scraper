"""/cutshort/locations, /cutshort/autocomplete, /cutshort/job-descriptions,
/cutshort/job-descriptions/details — the city vocabularies behind the
`location` params, the search box's suggestions (skills, companies, job
titles, locations) and the site's job description templates."""
from cutshort import fetch, refdata
from cutshort import parsers as P


def locations():
    """The 14 cities Cutshort lists jobs by (the `location` of
    /cutshort/jobs/search, /companies/directory, /jobs/categories) and the
    16 locations its salary pages cover (the `location` of /cutshort/salaries)."""
    cities = [{"slug": slug, "name": name, "alternate_names": list(alternates),
               "salary_location_slug": refdata.CITY_TO_SALARY_LOCATION.get(slug, slug)
               if refdata.CITY_TO_SALARY_LOCATION.get(slug, slug) in refdata.SALARY_LOCATIONS else None}
              for slug, (name, alternates) in refdata.CITIES.items()]
    salary = [{"slug": slug, "name": name, "site_name": site_name}
              for slug, (name, site_name) in refdata.SALARY_LOCATIONS.items()]
    return {"job_cities": cities, "salary_locations": salary, "count": len(cities)}


def autocomplete(query, type="skills", limit=10):
    """The search box's suggestions: skills (with codes and alternate
    spellings), companies (with the alias /companies/* takes), job titles
    (with their category and skill codes) or locations."""
    rows = fetch.algolia(refdata.ALGOLIA_INDICES[type], query, min(limit, 50))
    parser = {"skills": P.skill_suggestion, "companies": P.company_suggestion, "titles": P.title_suggestion,
              "locations": P.location_suggestion}[type]
    items = [parser(r) for r in rows if isinstance(r, dict)][:limit]
    return {"query": query, "type": type, "suggestions": items, "count": len(items)}


def job_descriptions():
    """The 98 role templates the site publishes (the `title` of
    /cutshort/job-descriptions/details)."""
    slugs = refdata.job_description_slugs()
    out = [{"slug": slug, "title": " ".join(w.capitalize() for w in slug.split("-")),
            "link": f"{refdata.BASE_URL}/job-description/{slug}"} for slug in slugs]
    return {"job_descriptions": out, "count": len(out)}


def job_description(title):
    """One role template: summary, the markdown brief (responsibilities,
    requirements), the matching jobs listing and related templates."""
    raw = fetch.job_description(title)
    out = P.job_description(raw, title)
    if not out.get("description_markdown"):
        raise fetch.CutshortNotFound(f"Cutshort has no job description for {title!r}; see /cutshort/job-descriptions")
    return out
