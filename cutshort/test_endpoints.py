"""Live endpoint smoke tests: one call per /cutshort/* route against a
running service, with example values proven to return data (2026-10-19).
The listing tooling (derive_facts.py) reads each route's FIRST call from
this file's AST as its working example, so the values stay literals.

Skipped unless CUTSHORT_BASE points at a running service:

    SCRAPERS_PORT=6113 ONLY_SCRAPER=cutshort python run.py
    CUTSHORT_BASE=http://127.0.0.1:6113 python -m pytest cutshort/test_endpoints.py -q
"""
import os

import pytest

BASE = os.environ.get("CUTSHORT_BASE", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="set CUTSHORT_BASE to run live endpoint tests")


def call(path, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=300)
    assert resp.status_code == 200, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


def status(path, **params):
    from curl_cffi import requests
    return requests.get(BASE + path, params=params, timeout=300).status_code


def test_job_search():
    body = call("/cutshort/jobs/search", query="python", location="pune")
    assert body["count"] > 100 and body["per_page"] == 50 and len(body["jobs"]) == 50 and body["next"]
    assert body["listing"]["slug"] == "python-jobs-in-pune" and body["listing"]["query_matched_by"] == "exact"
    job = body["jobs"][0]
    assert job["id"] and job["title"] and job["link"].startswith("https://cutshort.io/job/") and job["posted_on"]
    assert job["skills"] and job["company"]["name"] and job["description"] and job["salary"]["currency"]
    page2 = call("/cutshort/jobs/search", query="python", location="pune", page=2)
    assert page2["current_page"] == 2 and page2["jobs"][0]["id"] not in {j["id"] for j in body["jobs"]}
    body = call("/cutshort/jobs/search", query="React.js", remote="true", experience_years=3, min_salary_lakhs=10)
    assert body["listing"]["slug"] == "remote-reactjs-jobs" and body["jobs"] and body["jobs_on_page"] <= 50
    assert all(j["salary"]["max_lakhs"] >= 10 for j in body["jobs"])
    body = call("/cutshort/jobs/search", query="https://cutshort.io/jobs/remote-golang-jobs", page=2)
    assert body["listing"]["is_remote"] is True and body["listing"]["query_matched_by"] == "slug" and body["jobs"]
    body = call("/cutshort/jobs/search", query="product manager", location="gurgaon")
    assert body["listing"]["location_slug"] == "delhi-ncr-gurgaon-noida" and body["jobs"]
    body = call("/cutshort/jobs/search")
    assert body["listing"]["slug"] == "startup-jobs" and body["count"] > 10000
    assert status("/cutshort/jobs/search", query="zzqqxxnonsense") == 404
    assert status("/cutshort/jobs/search", location="Atlantis") == 400
    assert status("/cutshort/jobs/search", query="python", location="pune", remote="true") == 404


def test_job_details():
    body = call("/cutshort/jobs/details", job="https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2", include_similar="true")
    assert body["id"] == "I1i8FXO2" and body["title"] == "Full-Stack Software Engineer" and body["is_live"] is True
    assert body["salary"]["min_lakhs"] == 20.0 and body["experience"]["max_years"] == 14 and len(body["skills"]) == 19
    assert body["company"]["alias"] == "jobs-at-provenir-06-QcQfibQi" and body["company"]["faqs"] and body["recruiter"]["name"]
    assert body["category"] == "tech" and body["posted_on"] and len(body["similar_jobs"]) == 10
    bare = call("/cutshort/jobs/details", job="I1i8FXO2")
    assert bare["record_id"] == "6abe4d08f4afa2722c7a7b28" and bare["similar_jobs"] is None
    assert status("/cutshort/jobs/details", job="does-not-exist-XXXXXXXX") == 404
    assert status("/cutshort/jobs/details", job="abc") == 400


def test_job_batch_and_similar():
    body = call("/cutshort/jobs/batch", jobs="I1i8FXO2,6abe4d08f4afa2722c7a7b28,XXXXXXXX")
    assert body["count"] == 2 and body["errors"] == {"XXXXXXXX": "not found"}
    body = call("/cutshort/jobs/similar", job="I1i8FXO2")
    assert body["job"]["id"] == "I1i8FXO2" and body["count"] == 10 and body["jobs"][0]["company"]["name"]


def test_job_categories():
    body = call("/cutshort/jobs/categories", query="react", location="pune")
    assert body["count"] == 2 and body["categories"][0]["slug"] == "reactjs-jobs-in-pune" and body["source"] == "site"
    body = call("/cutshort/jobs/categories", remote="true", page=2)
    assert body["count"] > 50 and body["current_page"] == 2 and body["categories"][0]["is_remote"] is True
    body = call("/cutshort/jobs/categories")
    assert body["count"] > 20000 and body["total_pages"] > 400


def test_company_details_and_jobs():
    body = call("/cutshort/companies/details", company="Meesho")
    assert body["alias"] == "meesho-Xf1Xrsdc" and body["links"]["website"] == "https://meesho.com" and body["hiring_team"]
    assert body["jobs_count"] >= 1 and body["jobs"] and body["similar_companies"]
    body = call("/cutshort/companies/details", company="https://cutshort.io/company/jobs-at-wissen-technology-79-09J2iH1M", page=2)
    assert body["name"] == "Wissen Technology" and body["jobs_pagination"]["page"] == 2 and len(body["jobs"]) == 10
    body = call("/cutshort/companies/jobs", company="jobs-at-wissen-technology-79-09J2iH1M", page=3)
    assert body["count"] > 100 and body["per_page"] == 10 and body["current_page"] == 3 and body["next"]
    assert body["company"]["name"] == "Wissen Technology" and len(body["jobs"]) == 10
    body = call("/cutshort/companies/search", query="meesho", limit=3)
    assert body["count"] >= 1 and body["companies"][0]["alias"] == "meesho-Xf1Xrsdc"
    assert status("/cutshort/companies/details", company="zzz-nothing-XXXXXXXX") == 404
    assert status("/cutshort/companies/details", company="zzqqxx nonexistent corp") == 404


def test_company_directories():
    body = call("/cutshort/companies/directory", category="fintech", location="pune")
    assert body["directory"]["slug"] == "fintech-companies-in-pune" and len(body["companies"]) > 10
    assert body["companies"][0]["alias"] and body["companies"][0]["jobs_count"] is not None
    body = call("/cutshort/companies/directory", category="fintech")
    assert len(body["companies"]) == 50 and body["next"] and body["directory"]["location_slug"] is None
    body = call("/cutshort/companies/directory", location="bangalore")
    assert body["directory"]["slug"] == "startups-in-bengaluru" and body["companies"]
    body = call("/cutshort/companies/directory", category="https://cutshort.io/companies/saas-companies-in-chennai")
    assert body["directory"]["category"] == "saas" and body["directory"]["location_slug"] == "chennai"
    body = call("/cutshort/companies/directory", category="fintech", page=99)
    assert body["companies"] == [] and body["next"] is None
    assert status("/cutshort/companies/directory", category="fintech", location="bangalore") == 404
    assert status("/cutshort/companies/directory", category="zzz") == 404
    body = call("/cutshort/companies/categories", location="pune")
    assert body["count"] > 50 and body["directories"][0]["location_slug"] == "pune"
    assert call("/cutshort/companies/categories")["count"] > 500


def test_salaries():
    body = call("/cutshort/salaries", title="Python Developer", location="Bengaluru")
    assert body["title_slug"] == "python-developer" and body["location_slug"] == "bangalore"
    assert body["percentiles"]["top_10_percent"]["lakhs_per_year"] > 5 and body["trends"]["by_city"] and body["faqs"]
    body = call("/cutshort/salaries", title="https://cutshort.io/salary/data-scientist/remote")
    assert body["is_remote"] is True and body["title"] == "Data Scientist"
    body = call("/cutshort/salaries", title="data-scientist")
    assert body["location_slug"] == "india"
    assert status("/cutshort/salaries", title="zzz") == 400
    body = call("/cutshort/salaries/titles", location="pune")
    assert body["count"] == 37 and body["titles"][0]["locations"] == ["pune"]


def test_job_descriptions():
    body = call("/cutshort/job-descriptions")
    assert body["count"] == 98 and body["job_descriptions"][0]["slug"]
    body = call("/cutshort/job-descriptions/details", title="Python Developer")
    assert body["slug"] == "python-developer" and body["description_markdown"].startswith("## ") and body["related"]
    assert status("/cutshort/job-descriptions/details", title="zzz-nothing") == 404


def test_lookups():
    body = call("/cutshort/locations")
    assert body["count"] == 14 and body["job_cities"][0]["slug"] == "bangalore-bengaluru" and len(body["salary_locations"]) == 16
    body = call("/cutshort/autocomplete", query="pyth", type="skills", limit=5)
    assert body["suggestions"][0]["name"] == "Python" and body["suggestions"][0]["code"] == "00360"
    body = call("/cutshort/autocomplete", query="mees", type="companies")
    assert body["suggestions"][0]["alias"] == "meesho-Xf1Xrsdc"
    body = call("/cutshort/autocomplete", query="react", type="titles")
    assert body["suggestions"][0]["tags"]
    body = call("/cutshort/autocomplete", query="pune", type="locations")
    assert body["suggestions"][0]["name"] == "Pune"
    assert status("/cutshort/autocomplete", query="x", type="cities") == 400
