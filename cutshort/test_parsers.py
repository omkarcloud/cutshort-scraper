"""Offline tests: refs resolvers, marshmallow schemas, value helpers, parsers
and the endpoint functions with the transport monkeypatched to serve
fixtures (cutshort/fixtures/*.gz, raw payloads captured 2026-10-19 from
cutshort.io) — no network.

    python -m pytest cutshort/test_parsers.py -q
"""
import gzip
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutshort import companies, fetch, jobs, lookups, parsers as P, refdata, refs, salaries, schemas, shared as S  # noqa: E402
from schema_fields import load_query  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fx(name):
    with gzip.open(os.path.join(FX, name + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


def fx_html(name):
    with gzip.open(os.path.join(FX, name + ".html.gz"), "rt", encoding="utf-8") as f:
        return f.read()


def data(name):
    """A backend envelope fixture -> its `data` (what fetch.webpage returns)."""
    return fx(name)["data"]


# ---- refs ------------------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("I1i8FXO2", "I1i8FXO2"),
    ("Full-Stack-Software-Engineer-Provenir-I1i8FXO2", "I1i8FXO2"),
    ("https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2", "I1i8FXO2"),
    ("cutshort.io/job/x-I1i8FXO2?ref=abc", "I1i8FXO2"),
    ("6abe4d08f4afa2722c7a7b28", "6abe4d08f4afa2722c7a7b28"),
])
def test_resolve_job(value, expected):
    assert refs.resolve_job(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "https://example.com/job/x-I1i8FXO2", "https://cutshort.io/company/x",
                                   "two words"])
def test_resolve_job_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_job(value)


def test_resolve_jobs():
    assert refs.resolve_jobs("I1i8FXO2, https://cutshort.io/job/a-b-p7PgIKOo,I1i8FXO2") == ["I1i8FXO2", "p7PgIKOo"]
    with pytest.raises(ValueError):
        refs.resolve_jobs(",".join(["a-%08d" % i for i in range(11)]))


@pytest.mark.parametrize("value, expected", [
    ("meesho-Xf1Xrsdc", {"alias": "meesho-Xf1Xrsdc", "name": None}),
    ("https://cutshort.io/company/jobs-at-provenir-06-QcQfibQi", {"alias": "jobs-at-provenir-06-QcQfibQi", "name": None}),
    ("skillstaffing-consultancy-services-(sscs)-pZ0UCnj0", {"alias": "skillstaffing-consultancy-services-(sscs)-pZ0UCnj0", "name": None}),
    ("b+m-surface-systems--22-mf5FmoLl", {"alias": "b+m-surface-systems--22-mf5FmoLl", "name": None}),
    ("Meesho", {"alias": None, "name": "Meesho"}),
    ("Wissen  Technology", {"alias": None, "name": "Wissen Technology"}),
])
def test_resolve_company(value, expected):
    assert refs.resolve_company(value) == expected


def test_resolve_company_rejects():
    for value in ("", "https://cutshort.io/jobs/python-jobs", "https://example.com/company/x"):
        with pytest.raises(ValueError):
            refs.resolve_company(value)


@pytest.mark.parametrize("value, expected", [
    ("python", {"text": "python", "slug": None}),
    ("Python  Developer", {"text": "Python Developer", "slug": None}),
    ("python-jobs-in-pune", {"text": None, "slug": "python-jobs-in-pune"}),
    ("https://cutshort.io/jobs/remote-golang-jobs", {"text": None, "slug": "remote-golang-jobs"}),
    ("not-a-listing-jobs-xyz", {"text": "not-a-listing-jobs-xyz", "slug": None}),
    ("", None),
])
def test_resolve_query(value, expected):
    assert refs.resolve_query(value) == expected


def test_resolve_query_rejects():
    for value in ("https://cutshort.io/company/x", "https://example.com/jobs/python-jobs", "a/b"):
        with pytest.raises(ValueError):
            refs.resolve_query(value)


@pytest.mark.parametrize("value, expected", [
    ("pune", "pune"), ("Bangalore", "bangalore-bengaluru"), ("bengaluru", "bangalore-bengaluru"),
    ("Bangalore (Bengaluru)", "bangalore-bengaluru"), ("delhi ncr", "delhi-ncr-gurgaon-noida"),
    ("Gurgaon", "delhi-ncr-gurgaon-noida"), ("Kochi", "kochi-cochin"), ("india", None), ("", None),
    ("Delhi, NCR and Gurgaon", "delhi-ncr-gurgaon-noida"),
])
def test_resolve_location(value, expected):
    assert refs.resolve_location(value) == expected


def test_resolve_location_rejects():
    with pytest.raises(ValueError):
        refs.resolve_location("Atlantis")


@pytest.mark.parametrize("value, expected", [
    ("fintech", "fintech"), ("Fintech Companies", "fintech-companies"),
    ("https://cutshort.io/companies/fintech-companies-in-pune", "fintech-companies-in-pune"), ("", None),
])
def test_resolve_category(value, expected):
    assert refs.resolve_category(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("python-developer", {"title": "python-developer", "location": None}),
    ("Python Developer", {"title": "python-developer", "location": None}),
    ("python developer jobs", {"title": "python-developer", "location": None}),
    ("React.js Developer", {"title": "react-js-developer", "location": None}),
    ("https://cutshort.io/salary/data-scientist/remote", {"title": "data-scientist", "location": "remote"}),
    ("https://cutshort.io/salary/data-scientist", {"title": "data-scientist", "location": None}),
])
def test_resolve_salary_title(value, expected):
    assert refs.resolve_salary_title(value) == expected


def test_resolve_salary_title_rejects():
    with pytest.raises(ValueError):
        refs.resolve_salary_title("zzz")


@pytest.mark.parametrize("value, expected", [
    ("bangalore", "bangalore"), ("Bengaluru (Bangalore)", "bangalore"), ("bangalore-bengaluru", "bangalore"),
    ("Delhi NCR", "delhi-ncr"), ("gurgaon", "delhi-ncr"), ("india", "india"), ("remote", "remote"), ("wfh", "remote"),
    ("Kochi (Cochin)", "kochi"), ("", None),
])
def test_resolve_salary_location(value, expected):
    assert refs.resolve_salary_location(value) == expected


def test_resolve_job_description():
    assert refs.resolve_job_description("Python Developer") == "python-developer"
    assert refs.resolve_job_description("https://cutshort.io/job-description/backend-developer") == "backend-developer"
    assert refs.resolve_job_description("zzz nothing") == "zzz-nothing"      # the site decides


# ---- schemas -------------------------------------------------------------------------------------

def test_job_search_schema():
    loaded, err = load_query(schemas.JobSearchSchema, {"query": "python", "location": "Pune", "remote": "true",
                                                       "experience_years": "3", "min_salary_lakhs": "12.5",
                                                       "role_type": "Full_Time", "skill": "python, Django"})
    assert err is None
    assert loaded["query"] == {"text": "python", "slug": None} and loaded["location"] == "pune"
    assert loaded["remote"] is True and loaded["experience_years"] == 3 and loaded["min_salary_lakhs"] == 12.5
    assert loaded["role_type"] == "full_time" and loaded["skill"] == ["python", "Django"] and loaded["page"] == 1
    _, err = load_query(schemas.JobSearchSchema, {"location": "Atlantis"})
    assert err and "location" in err["errors"]
    _, err = load_query(schemas.JobSearchSchema, {"company_type": "bank"})
    assert err and "company_type" in err["errors"]
    _, err = load_query(schemas.JobSearchSchema, {"typo": "x"})
    assert err


def test_other_schemas():
    loaded, err = load_query(schemas.JobSchema, {"job": "I1i8FXO2"})
    assert err is None and loaded == {"job": "I1i8FXO2", "include_similar": False}
    _, err = load_query(schemas.JobSchema, {})
    assert err and "job" in err["errors"]
    loaded, err = load_query(schemas.CompanySchema, {"company": "Meesho", "page": "2"})
    assert err is None and loaded == {"company": {"alias": None, "name": "Meesho"}, "page": 2}
    loaded, err = load_query(schemas.SalarySchema, {"title": "Python Developer", "location": "Bengaluru"})
    assert err is None and loaded == {"title": {"title": "python-developer", "location": None}, "location": "bangalore"}
    loaded, err = load_query(schemas.AutocompleteSchema, {"query": "py", "type": "Titles"})
    assert err is None and loaded["type"] == "titles"
    _, err = load_query(schemas.AutocompleteSchema, {"query": "py", "type": "cities"})
    assert err
    loaded, err = load_query(schemas.DirectorySchema, {"category": "fintech", "location": "pune"})
    assert err is None and loaded == {"category": "fintech", "location": "pune", "page": 1}


# ---- shared -----------------------------------------------------------------------------------------

def test_shared_helpers():
    assert S.num("1,234.5") == 1234.5 and S.num(True) is None and S.to_int("3.6") == 4
    assert S.lakhs(2500000) == 25.0 and S.lakhs(None) is None
    assert S.text("  a &amp; b  ") == "a & b" and S.text("") is None
    assert S.slugify("Python Developer!") == "python-developer" and S.compact("React.js") == "reactjs"
    assert S.iso_date("2026-10-06T09:26:21.519Z") == "2026-10-06" and S.iso_datetime("2026-10-06T09:26:21.519Z") == "2026-10-06T09:26:21Z"
    assert S.link("/jobs/python-jobs") == "https://cutshort.io/jobs/python-jobs" and S.link(None) is None
    assert S.job_short_id("https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2") == "I1i8FXO2"
    assert S.html_to_text("<p>Hi<br/>there</p><ul><li>one</li><li>two</li></ul>") == "Hi\nthere\n- one\n- two"
    assert S.html_fragment("<p><br /></p>") is None and S.html_fragment("<p>x</p>") == "<p>x</p>"


def test_salary_text():
    assert P.salary_text("₹20L - ₹40L / yr") == {"currency": "INR", "min": 2000000.0, "max": 4000000.0, "per": "year", "text": "₹20L - ₹40L / yr"}
    assert P.salary_text("Upto ₹12L / yr")["min"] is None and P.salary_text("Upto ₹12L / yr")["max"] == 1200000.0
    assert P.salary_text("$80K - $120K / yr")["currency"] == "USD" and P.salary_text("$80K - $120K / yr")["max"] == 120000.0
    assert P.salary_text("Best in industry") is None and P.salary_text(None) is None
    band = P.salary_band({"currency": "INR", "min": 0, "max": 2200000, "userMin": 0, "userMax": 2200000}, "₹1L - ₹22L / yr")
    assert band["min"] is None and band["max_lakhs"] == 22.0 and band["text"] == "₹1L - ₹22L / yr" and band["has_esop"] is False
    band = P.salary_band({"currency": "INR", "min": 1500000, "max": 6000000, "userMin": 1500000, "userMax": 6000000,
                          "minVanity": 3000000, "maxVanity": 0}, "₹30L - ₹60L / yr (ESOP available)")
    assert band["min_lakhs"] == 30.0 and band["max_lakhs"] == 60.0 and band["has_esop"] is True
    band = P.salary_band({"currency": "INR", "min": 0, "max": 0, "minVanity": 0, "maxVanity": 0}, "₹0L / yr (ESOP available)")
    assert band["min"] is None and band["max"] is None and band["has_esop"] is True and band["text"] == "₹0L / yr (ESOP available)"
    band = P.salary_band("₹0L / yr (ESOP available)")
    assert band["min"] is None and band["max"] is None and band["has_esop"] is True
    band = P.salary_band("₹30L - ₹60L / yr (ESOP available)")
    assert band["min_lakhs"] == 30.0 and band["max_lakhs"] == 60.0 and band["has_esop"] is True
    band = P.salary_band("Best in industry")
    assert band["min"] is None and band["text"] == "Best in industry"
    assert P.salary_band(None) is None and P.salary_band({}, None) is None
    links = P.links_of({"website": "https://paytm.com", "about": "https://paytm.com/about-us", "youtubeVideo": "https://youtube.com/watch",
                        "team": "https://atlassian.com/teams/hr", "linkedin": "https://linkedin.com", "articles": []})
    assert links["about"] == "https://paytm.com/about-us" and links["team"] == "https://atlassian.com/teams/hr"
    assert links["youtube_video"] is None and links["linkedin"] is None and links["website"] == "https://paytm.com"
    band = P.salary_band({"currency": "INR", "min": 0, "max": 2200000, "minVanity": 100000, "maxVanity": 2200000}, "₹1L - ₹22L / yr")
    assert band["min_lakhs"] == 1.0


# ---- refdata catalogue ----------------------------------------------------------------------------------

def test_catalogue():
    cat = refdata.catalogue()
    assert cat.has("python-jobs-in-pune") and cat.has("remote-reactjs-jobs") and not cat.has("react-jobs-in-pune")
    assert cat.weight("python") == 16 and cat.weight("nope") == 0
    assert cat.by_compact("reactjs") == ["reactjs"] and cat.topic_label("python") == "Python Jobs"
    assert refdata.parse_listing_slug("remote-python-jobs-in-pune") == ("python", "pune", True)
    assert refdata.parse_listing_slug("startup-jobs") == ("startup", None, False)
    assert refdata.parse_listing_slug("fintech") is None
    assert refdata.build_listing_slug("python", "pune", True) == "remote-python-jobs-in-pune"
    assert len(refdata.company_listing_labels()) == 563 and len(refdata.salary_titles()) == 37
    assert refdata.salary_titles()["python-developer"] == "Python Developer"
    assert len(refdata.job_description_slugs()) == 98


# ---- parsers ----------------------------------------------------------------------------------------

def test_job_card():
    card = P.job_card(data("job_list")["pageData"]["jobs"][0])
    assert card["id"] == "I1i8FXO2" and card["record_id"] == "6abe4d08f4afa2722c7a7b28"
    assert card["title"] == "Full-Stack Software Engineer" and card["link"].endswith("-I1i8FXO2")
    assert card["company"]["name"] == "Provenir" and card["company"]["alias"] == "jobs-at-provenir-06-QcQfibQi"
    assert card["recruiting_company"] is None
    masked = [P.job_card(j) for j in data("job_list")["pageData"]["jobs"] if j.get("hiringForClient")][0]
    assert masked["company"]["alias"] is None and masked["recruiting_company"]["name"] == "Peak Hire Solutions"
    assert card["company"]["type"] == "Product" and card["company"]["size"] == "100-500" and card["company"]["stage"] == "Profitable"
    assert card["company"]["funding"] == "Profitable" and card["company"]["founded_year"] == 2004
    assert card["locations"] == [] and card["is_remote"] is True and card["remote_policy"] == "remote"
    assert card["role_types"] == ["full_time"] and card["is_internship"] is False
    assert card["experience"] == {"min_years": 4.0, "max_years": 14.0, "text": "4 - 14 years"}
    assert card["salary"]["min_lakhs"] == 20.0 and card["salary"]["max_lakhs"] == 40.0 and card["salary"]["currency"] == "INR"
    assert card["skills"][1] == {"code": "00236", "name": "Java"} and len(card["skills"]) == 19
    assert card["posted_at"] == "2026-10-01T12:07:36Z" and card["posted_on"] == "2026-10-01"
    assert card["description"].startswith("**Please apply directly") and card["description_html"].startswith("<p>")
    assert card["recruiter"]["name"] == "Chloe Densham"
    assert card["related_listings"] == [{"label": "Fullstack Developer Jobs in India", "link": "https://cutshort.io/jobs/fullstack-developer-jobs", "slug": "fullstack-developer-jobs"}]
    assert "authApplyUrl" not in json.dumps(card) and "Vanity" not in json.dumps(card)


def test_job_card_partial():
    card = P.job_card({"headline": "X"})
    assert card["title"] == "X" and card["id"] is None and card["company"] is None and card["salary"] is None
    assert P.job_card({}) ["title"] is None


def test_listing_page():
    page = P.listing_page(data("job_list_combo"), "python-jobs-in-bangalore-bengaluru", 1)
    assert page["pagination"] == {"page": 1, "items_per_page": 50, "total_pages": 37, "total_count": 1824}
    assert len(page["jobs"]) == 50 and page["listing"]["title"].startswith("1824+ Python Jobs")
    assert page["jobs"][1]["locations"] == ["Bengaluru (Bangalore)", "Pune", "Hyderabad", "Chennai"]
    menus = page["related_listings"]
    assert menus[0]["title"] == "Python jobs in other cities" and menus[0]["links"][0]["slug"].startswith("remote-python") or menus[0]["links"][0]["slug"]
    grouped = [m for m in menus if m["title"] == "Jobs by Category"][0]
    assert grouped["links"][0]["group"] == "Tech Jobs" and grouped["links"][0]["slug"] == "fullstack-developer-jobs"


def test_job_details():
    out = P.job_details(data("job_detail"), fx("similar_jobs")["jobs"])
    assert out["id"] == "I1i8FXO2" and out["is_live"] is True and out["category"] == "tech" and out["tags"] == ["fullstack"]
    assert out["salary"] == {"currency": "INR", "min": 2000000.0, "max": 4000000.0, "min_lakhs": 20.0, "max_lakhs": 40.0,
                             "per": "year", "has_esop": False, "text": "₹20L - ₹40L / yr"}
    assert out["experience"]["max_years"] == 14.0 and out["locations"] == [] and out["is_remote"] is True
    assert out["posted_on"] == "2026-10-06" and out["shows_only_max_salary"] is False and out["client_company"] is None
    assert out["company"]["name"] == "Provenir" and out["company"]["faqs"][0]["answer"] == "Bangalore/ remote India"
    assert out["company"]["website"] == "https://provenir.com/careers" and out["company"]["description"].startswith("Provenir is")
    assert len(out["similar_jobs"]) == 10 and out["similar_jobs"][0]["company"]["name"] == "MNC"
    assert out["similar_jobs"][0]["is_hiring_for_client"] is True
    assert out["similar_jobs"][0]["recruiting_company"]["name"] == "VY SYSTEMS PRIVATE LIMITED"
    assert out["recruiting_company"] is None
    assert out["similar_jobs"][0]["salary"]["min_lakhs"] == 1.0 and out["similar_jobs"][0]["salary"]["max_lakhs"] == 22.0
    assert P.job_details(data("job_detail"))["similar_jobs"] is None
    assert "USMReview" not in json.dumps(out) and "jsonlds" not in json.dumps(out)


def test_company_profile():
    out = P.company_profile(data("company_big"), "meesho-Xf1Xrsdc")
    assert out["name"] == "Meesho" and out["alias"] == "meesho-Xf1Xrsdc" and out["link"] == "https://cutshort.io/company/meesho-Xf1Xrsdc"
    assert out["type"] == "Product" and out["stage"] == "Raised funding" and out["funding"] == "Raised funding"
    assert out["size"] == "1000-5000" and out["founded_year"] == 2015 and out["domains"] == ["ecommerce"]
    assert out["links"]["website"] == "https://meesho.com" and out["links"]["ambitionbox"] == "https://ambitionbox.com/meesho"
    assert out["links"]["instagram"] is None and out["jobs_count"] == 6
    assert len(out["team"]) == 7 and out["team"][0]["name"] == "Deepa Shankar" and out["team"][0]["linkedin"] is None
    assert len(out["hiring_team"]) == 7 and out["jobs"] == [] and out["jobs_pagination"]["page"] == 2
    assert len(out["similar_companies"]) == 10 and out["similar_companies"][0]["alias"] == "getmeashopcom-ox6wyxHc"
    small = P.company_profile(data("company"), "jobs-at-provenir-06-QcQfibQi")
    assert small["size"] == "100-500" and small["stage"] == "Profitable" and len(small["jobs"]) == 1
    assert small["faqs"][0]["question"] == "What is the location preference of jobs?" and small["jobs_pagination"]["total_pages"] == 1
    assert "allUsersOnNonPaidPlan" not in json.dumps(out) and "sectionsEnabled" not in json.dumps(out)


def test_directory_page():
    out = P.directory_page(data("companies_dir"), "fintech", 1)
    assert out["directory"]["title"] == "Fintech Companies/Startups in India" and len(out["companies"]) == 50
    first = out["companies"][0]
    assert first["name"] == "Wissen Technology" and first["jobs_count"] == 598 and first["type"] == "Products & Services"
    assert first["size"] == "1000-5000" and first["website"] == "https://wissen.com" and first["description"].startswith("The Wissen Group")
    assert out["related_directories"][0]["links"][0]["slug"] == "fintech-companies-in-ahmedabad"


def test_categories_page():
    out = P.categories_page(data("jobs_index"), 1)
    assert out["pagination"]["total_count"] == 3779 and out["pagination"]["items_per_page"] == 15 and out["pagination"]["total_pages"] == 252
    assert out["categories"][0]["slug"] == "2d-animation-jobs-in-ahmedabad" and out["categories"][0]["location"] == "Ahmedabad"
    featured = out["featured"][0]
    assert featured["slug"] == "remote-golang-jobs" and featured["is_remote"] is True and featured["skill_codes"] == ["00186"]
    assert featured["title"] == "Remote Golang & Go Programming Jobs"


def test_sitemap_catalogue():
    rows = P.sitemap_catalogue(data("sitemap"))
    assert len(rows["jobs"]) == 20937 and len(rows["companies"]) == 563 and len(rows["salaries"]) == 592
    assert ["python-jobs-in-pune", "Python Jobs in Pune"] in rows["jobs"]
    assert ["python-developer/pune", "Salary for Python Developer in Pune"] in rows["salaries"]
    assert ["android-developer", "Salary for Android Developer in India"] in rows["salaries"]


def test_job_description():
    out = P.job_description(data("job_description"), "python-developer")
    assert out["title"] == "Python Developer" and out["summary"].startswith("A Python developer")
    assert out["description_markdown"].startswith("## Python Developer Job Brief") and out["jobs_listing"]["slug"] == "python-jobs"
    assert out["related"][0] == {"slug": "java-developer", "title": "Java Developer", "link": "https://cutshort.io/job-description/java-developer",
                                 "logo": "https://cutshort.io/job-description/java-developer-logo.webp"}
    assert "caseStudy" not in json.dumps(out) and "testimonials" not in json.dumps(out)


def test_salary_page():
    out = P.salary_page(fx_html("salary_page"), "python-developer", "bangalore")
    assert out["title"] == "Python Developer" and out["location"] == "Bangalore" and out["is_remote"] is False
    assert out["percentiles"]["top_5_percent"]["lakhs_per_year"] == 30.0 and out["percentiles"]["top_20_percent"]["lakhs_per_year"] == 12.0
    assert out["experience_years"] == 2 and out["tag"] == "backend" and out["category"] == "tech"
    assert out["trends"]["by_city"][0] == {"slug": "bangalore", "label": "Bangalore", "lakhs_per_year": 18.0}
    assert out["trends"]["by_role"][0]["label"] == "Backend developer"
    assert out["faqs"][0]["answer"] == "The starting salary of python developers in Bangalore is ₹12 Lakhs per annum."
    assert out["related_pages"][0]["location_slug"] == "ahmedabad" and out["related_pages"][0]["median_lakhs_per_year"] == 12.2
    remote = P.salary_page(fx_html("salary_page_remote"), "python-developer", "remote")
    assert remote["is_remote"] is True and remote["location_slug"] == "remote"
    assert P.salary_page("<html></html>", "x", "y") is None
    lists = P.salary_lists(fx_html("salary_page"))
    assert len(lists["locations"]) == 16 and lists["role_categories"][0]["roles"][0]["tag"] == "backend"


def test_suggestions():
    skill = P.skill_suggestion(fx("algolia_skills")["hits"][0])
    assert skill["code"] == "00368" and skill["name"] == "React.js" and skill["alternate_names"] == ["ReactJS", "React"]
    company = P.company_suggestion(fx("algolia_companies")["hits"][0])
    assert company["alias"] == "meesho-Xf1Xrsdc" and company["size"] == "500-1000" and company["type"] == "Product"
    assert P.company_suggestion(fx("algolia_companies")["hits"][1])["website"] == "https://www.melshotels.com/"
    title = P.title_suggestion(fx("algolia_titles")["hits"][0])
    assert title["name"] == "React Native Developer" and title["tags"] == ["mobile"]
    loc = P.location_suggestion(fx("algolia_locations")["hits"][0])
    assert loc["name"] == "Pune" and loc["code"] == "001685"


# ---- endpoint functions over fixtures ----------------------------------------------------------------------

@pytest.fixture
def offline(monkeypatch):
    calls = []

    def listing(slug, page=1):
        calls.append(("listing", slug, page))
        if slug == "python-jobs-in-bangalore-bengaluru":
            if page > 1:
                raise fetch.PastEnd("past")
            return data("job_list_combo")
        if slug == "software-development-jobs":
            return data("job_list")
        raise fetch.CutshortNotFound("no " + slug)

    def job(ref):
        calls.append(("job", ref))
        if ref in ("I1i8FXO2", "6abe4d08f4afa2722c7a7b28"):
            return data("job_detail")
        raise fetch.CutshortNotFound("no " + ref)

    def company(alias, page=1):
        calls.append(("company", alias, page))
        if alias == "meesho-Xf1Xrsdc":
            return data("company_big")
        if alias == "jobs-at-provenir-06-QcQfibQi":
            return data("company")
        raise fetch.CutshortNotFound("no " + alias)

    def directory(slug, page=1):
        calls.append(("directory", slug, page))
        if slug == "fintech" and page == 1:
            return data("companies_dir")
        if slug == "fintech":
            raise fetch.PastEnd("past")
        raise fetch.CutshortNotFound("no " + slug)

    def algolia(index, query, hits=10):
        calls.append(("algolia", index, query))
        if query.lower()[:4] not in ("reac", "mees", "pyth", "pune"):
            return []
        return {"prod_skills": fx("algolia_skills"), "prod_companies": fx("algolia_companies"),
                "prod_headlines": fx("algolia_titles"), "prod_locations": fx("algolia_locations")}[index]["hits"]

    monkeypatch.setattr(fetch, "listing", listing)
    monkeypatch.setattr(fetch, "job", job)
    monkeypatch.setattr(fetch, "similar_jobs", lambda record_id: fx("similar_jobs")["jobs"])
    monkeypatch.setattr(fetch, "company", company)
    monkeypatch.setattr(fetch, "directory", directory)
    monkeypatch.setattr(fetch, "algolia", algolia)
    monkeypatch.setattr(fetch, "sitemap", lambda: data("sitemap"))
    monkeypatch.setattr(fetch, "job_description", lambda slug: data("job_description") if slug == "python-developer" else (_ for _ in ()).throw(fetch.CutshortNotFound(slug)))
    monkeypatch.setattr(fetch, "salary_page", lambda title, loc: fx_html("salary_page_remote" if loc == "remote" else "salary_page"))
    monkeypatch.setattr(fetch, "shared_raw", lambda name, params, build, ttl: build())
    return calls


def test_jobs_search(offline):
    out = jobs.search(query={"text": "Python", "slug": None}, location="bangalore-bengaluru")
    assert out["listing"]["slug"] == "python-jobs-in-bangalore-bengaluru" and out["listing"]["query_matched_by"] == "exact"
    assert out["pagination"]["total_count"] == 1824 and len(out["jobs"]) == 50 and out["jobs_on_page"] == 50
    out = jobs.search(query={"text": "python", "slug": None}, location="bangalore-bengaluru", page=2)
    assert out["jobs"] == [] and out["pagination"]["total_pages"] == 1
    out = jobs.search(query={"text": None, "slug": "software-development-jobs"}, experience_years=5, min_salary_lakhs=30)
    assert out["jobs_on_page"] < 50 and all(j["salary"]["max_lakhs"] >= 30 for j in out["jobs"])
    assert all(j["experience"]["min_years"] <= 5 <= j["experience"]["max_years"] for j in out["jobs"])
    out = jobs.search(query={"text": None, "slug": "software-development-jobs"}, remote_policy="remote", skill=["java"])
    assert out["jobs"] and all(j["remote_policy"] == "remote" for j in out["jobs"])
    assert all(any(s["name"] == "Java" for s in j["skills"]) for j in out["jobs"])
    with pytest.raises(fetch.CutshortNotFound) as err:
        jobs.search(query={"text": "python", "slug": None}, location="pune", remote=True)
    assert "python-jobs-in-pune" in str(err.value)
    with pytest.raises(fetch.CutshortNotFound):
        jobs.search(query={"text": "zzqqxx", "slug": None})


def test_resolve_topic(offline):
    assert jobs.resolve_topic("Python Developer") == ("python", "exact")
    assert jobs.resolve_topic("react.js") == ("reactjs", "exact")
    assert jobs.resolve_topic("Senior React Native Engineer") == ("react-native", "exact")
    assert jobs.resolve_topic("product manager") == ("product-manager", "exact")
    assert jobs.resolve_topic("machine learning") == ("machine-learning-ml", "fuzzy")
    assert jobs.resolve_topic("zzqqxx") == (None, None)


def test_jobs_details_batch_similar(offline):
    out = jobs.details("I1i8FXO2", include_similar=True)
    assert out["title"] == "Full-Stack Software Engineer" and len(out["similar_jobs"]) == 10
    out = jobs.batch(["I1i8FXO2", "XXXXXXXX"])
    assert out["count"] == 1 and out["errors"] == {"XXXXXXXX": "not found"}
    out = jobs.similar("I1i8FXO2")
    assert out["count"] == 10 and out["job"]["record_id"] == "6abe4d08f4afa2722c7a7b28"
    with pytest.raises(fetch.CutshortNotFound):
        jobs.details("XXXXXXXX")


def test_jobs_categories(offline):
    out = jobs.categories(query={"text": "react", "slug": None}, location="pune")
    assert out["source"] == "site" and [c["slug"] for c in out["categories"]] == ["reactjs-jobs-in-pune", "react-native-jobs-in-pune"]
    assert out["categories"][0]["title"] == "React.js Jobs in Pune"
    out = jobs.categories(remote=True, page=2)
    assert out["pagination"]["total_count"] == 64 and out["pagination"]["total_pages"] == 2 and len(out["categories"]) == 14
    out = jobs.categories(query={"text": None, "slug": "python-jobs"})
    assert out["pagination"]["total_count"] == 1 and out["categories"][0]["topic"] == "python"


def test_companies(offline):
    out = companies.details({"alias": None, "name": "Meesho"})
    assert out["alias"] == "meesho-Xf1Xrsdc" and out["name"] == "Meesho" and out["jobs_count"] == 6
    out = companies.open_jobs({"alias": "jobs-at-provenir-06-QcQfibQi", "name": None})
    assert out["company"]["name"] == "Provenir" and len(out["jobs"]) == 1 and out["pagination"]["total_count"] == 1
    out = companies.search("meesho", limit=1)
    assert out["count"] == 1 and out["companies"][0]["alias"] == "meesho-Xf1Xrsdc"
    with pytest.raises(fetch.CutshortNotFound):
        companies.details({"alias": "zzz-nothing-XXXXXXXX", "name": None})


def test_directories(offline):
    out = companies.directory(category="fintech")
    assert out["directory"]["category"] == "fintech" and len(out["companies"]) == 50 and out["pagination"]["total_pages"] == 2
    out = companies.directory(category="fintech", page=2)
    assert out["companies"] == [] and out["pagination"]["total_pages"] == 1
    assert companies.directory_slug("fintech", "pune", refdata.company_listing_labels()) == "fintech-companies-in-pune"
    assert companies.directory_slug("startups", "bangalore-bengaluru", refdata.company_listing_labels()) == "startups-in-bengaluru"
    with pytest.raises(fetch.CutshortNotFound) as err:
        companies.directory(category="fintech", location="bangalore-bengaluru")
    assert "Cities with one" in str(err.value)
    out = companies.categories(location="pune")
    assert out["count"] == 63 and out["directories"][0]["location_slug"] == "pune"
    assert companies.categories()["count"] == 563


def test_salaries_and_lookups(offline):
    out = salaries.details({"title": "python-developer", "location": None}, "bangalore")
    assert out["percentiles"]["top_10_percent"]["lakhs_per_year"] == 18.0
    out = salaries.details({"title": "python-developer", "location": "remote"})
    assert out["is_remote"] is True
    out = salaries.titles(location="pune")
    assert out["count"] == 37 and out["titles"][0]["locations"] == ["pune"] and len(out["locations"]) == 16
    out = lookups.locations()
    assert out["count"] == 14 and out["job_cities"][0]["salary_location_slug"] == "bangalore"
    out = lookups.autocomplete("pyth", "companies", 2)
    assert out["count"] == 2 and out["suggestions"][0]["alias"]
    out = lookups.job_descriptions()
    assert out["count"] == 98
    out = lookups.job_description("python-developer")
    assert out["title"] == "Python Developer"
    with pytest.raises(fetch.CutshortNotFound):
        lookups.job_description("zzz")


def test_fetch_unwrap():
    assert fetch._unwrap(fx("job_list"), "x")["pageData"]["liveJobCount"] == 301
    with pytest.raises(fetch.PastEnd):
        fetch._unwrap(fx("job_list_not_found"), "x")
    with pytest.raises(fetch.CutshortNotFound):
        fetch._unwrap(fx("job_list_unknown"), "x")
    with pytest.raises(fetch.CutshortNotFound):
        fetch._unwrap(fx("job_not_found"), "x")
    with pytest.raises(fetch.CutshortUpstreamError):
        fetch._unwrap("nope", "x")
