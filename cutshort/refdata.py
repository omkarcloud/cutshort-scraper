"""Reference tables for the Cutshort scraper: the site's own enumerations
(company type / size / stage / funding codes from its staticAppConfig, the
remote-policy and role-type codes), the 14 job cities and the 16 salary
locations with their alternate spellings, and the listing catalogue —
every job listing slug (`<topic>-jobs[-in-<city>]`, optionally
`remote-` prefixed), company directory slug, salary page and job
description page the site has, with the labels the site gives them
(catalogue.json.gz, a snapshot of /backend-api/webpage/sitemap +
sitemap_job_descriptions.xml captured 2026-10-19). The catalogue is
refreshed live and cached at call time (lookups.py); the snapshot resolves
free text offline and stands in when the site does not answer."""
import gzip
import json
import os
import re
import threading

HOST = "cutshort.io"
BASE_URL = f"https://{HOST}"

# Every /backend-api/webpage/jobs/<slug> page carries 50 cards; a page past
# the end answers `jobs_not_found`. Company pages list 10 jobs a page,
# company directories 50 companies a page.
PAGE_SIZE = 50
COMPANY_JOBS_PAGE_SIZE = 10
DIRECTORY_PAGE_SIZE = 50
CATEGORIES_PAGE_SIZE = 50
MAX_PAGE = 1000
MAX_BATCH = 10
DEFAULT_CURRENCY = "INR"
LAKH = 100_000

# The hub listing every other listing is a subset of (44,000+ live jobs).
ALL_JOBS_TOPIC = "startup"

# Algolia (the site's search box; the search-only key is public in every
# page's staticAppConfig.algolia_frontend_keys).
ALGOLIA_APP_ID = "014RPJEKBQ"
ALGOLIA_SEARCH_KEY = "8cddd40d7437af1c3121d4511423f913"
ALGOLIA_INDICES = {"skills": "prod_skills", "companies": "prod_companies", "titles": "prod_headlines",
                   "locations": "prod_locations"}

# ---- job listing cities: slug -> (display name, alternate spellings) -----------------------------
CITIES = {
    "bangalore-bengaluru": ("Bangalore (Bengaluru)", ("bangalore", "bengaluru", "blr")),
    "mumbai": ("Mumbai", ("bombay",)),
    "delhi-ncr-gurgaon-noida": ("Delhi, NCR and Gurgaon", ("delhi", "ncr", "delhi ncr", "delhi-ncr", "delhi/ncr",
                                                           "gurgaon", "gurugram", "noida", "new delhi", "faridabad",
                                                           "ghaziabad")),
    "hyderabad": ("Hyderabad", ("secunderabad",)),
    "pune": ("Pune", ("poona",)),
    "chennai": ("Chennai", ("madras",)),
    "ahmedabad": ("Ahmedabad", ()),
    "kolkata": ("Kolkata", ("calcutta",)),
    "jaipur": ("Jaipur", ()),
    "indore": ("Indore", ()),
    "coimbatore": ("Coimbatore", ()),
    "kochi-cochin": ("Kochi (Cochin)", ("kochi", "cochin")),
    "chandigarh": ("Chandigarh", ("mohali", "panchkula")),
    "bhubaneswar": ("Bhubaneswar", ("bhubaneshwar",)),
}

# ---- salary page locations: slug -> (display name, the site's own name) -------------------------
SALARY_LOCATIONS = {
    "india": ("India", "India"),
    "remote": ("Remote", "Remote"),
    "mumbai": ("Mumbai", "Mumbai"),
    "pune": ("Pune", "Pune"),
    "bangalore": ("Bangalore", "Bengaluru (Bangalore)"),
    "delhi-ncr": ("Delhi NCR", "NCR (Delhi | Gurgaon | Noida)"),
    "hyderabad": ("Hyderabad", "Hyderabad"),
    "chennai": ("Chennai", "Chennai"),
    "coimbatore": ("Coimbatore", "Coimbatore"),
    "ahmedabad": ("Ahmedabad", "Ahmedabad"),
    "kolkata": ("Kolkata", "Kolkata"),
    "indore": ("Indore", "Indore"),
    "jaipur": ("Jaipur", "Jaipur"),
    "chandigarh": ("Chandigarh", "Chandigarh"),
    "kochi": ("Kochi (Cochin)", "Kochi (Cochin)"),
    "bhubaneswar": ("Bhubaneswar", "Bhubaneswar"),
}
# job city slug -> salary location slug (the two vocabularies differ)
CITY_TO_SALARY_LOCATION = {"bangalore-bengaluru": "bangalore", "delhi-ncr-gurgaon-noida": "delhi-ncr",
                           "kochi-cochin": "kochi"}

# ---- the site's codes ----------------------------------------------------------------------------
REMOTE_TYPES = {"remote_only": "remote", "remote_okay": "hybrid", "remote_not_okay": "onsite"}
ROLE_TYPES = {"full_time": "full_time", "internship": "internship"}
COMPANY_TYPES = {"1": "Product", "2": "Services", "3": "Products & Services", "product": "Product",
                 "service": "Services", "agency": "Agency"}
COMPANY_FUNDINGS = {"1": "Bootstrapped", "2": "Raised funding", "3": "Profitable"}
COMPANY_STAGES = {"1": "Bootstrapped", "2": "Raised funding", "3": "Profitable"}
# newSize codes (type_based_company_sizes) -> the size band
COMPANY_SIZES = {"prod_1": "0-20", "prod_2": "20-100", "prod_3": "100-500", "prod_4": "500-1000",
                 "prod_5": "1000-5000", "prod_6": "5000+",
                 "service_1": "0-20", "service_2": "20-100", "service_3": "100-1000", "service_4": "1000-5000",
                 "service_5": "5000+",
                 "agency_1": "0-10", "agency_2": "10-50", "agency_3": "50-200", "agency_4": "200-500",
                 "agency_5": "500+"}
# Algolia prod_companies `size` (1..6, product bands) and `type` (1..3)
ALGOLIA_COMPANY_SIZES = {1: "0-20", 2: "20-100", 3: "100-500", 4: "500-1000", 5: "1000-5000", 6: "5000+"}

# public filter vocabularies
COMPANY_TYPE_FILTERS = ("product", "services", "agency")
ROLE_TYPE_FILTERS = ("full_time", "internship")
REMOTE_FILTERS = ("remote", "hybrid", "onsite")

# ---- the catalogue -------------------------------------------------------------------------------
_CATALOGUE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogue.json.gz")
_SLUG_RE = re.compile(r"^(remote-)?(.+?)-jobs(?:-in-(.+))?$")
_lock = threading.RLock()
_snapshot = None


def snapshot():
    """The packaged catalogue: {"captured", "jobs": [[slug, label]…],
    "companies": [[slug, label]…], "salaries": [["<title>/<location>", label]…],
    "job_descriptions": [slug…]}."""
    global _snapshot
    with _lock:
        if _snapshot is None:
            with gzip.open(_CATALOGUE_PATH, "rt", encoding="utf-8") as f:
                _snapshot = json.load(f)
        return _snapshot


def parse_listing_slug(slug):
    """'remote-python-jobs-in-pune' -> ('python', 'pune', True); None when
    the slug is not a job listing slug."""
    match = _SLUG_RE.match(slug or "")
    if not match:
        return None
    remote, topic, city = match.groups()
    return topic, city, bool(remote)


def build_listing_slug(topic, city=None, remote=False):
    return f"{'remote-' if remote else ''}{topic}-jobs{'-in-' + city if city else ''}"


class JobCatalogue:
    """An index over the job listing slugs: topic -> its variants, labels."""

    def __init__(self, rows):
        self.labels = {}
        self.topics = {}            # topic -> {"cities": set, "remote": bool, "remote_cities": set}
        self.topic_labels = {}      # topic -> label of the plain '<topic>-jobs' page
        for slug, label in rows:
            parsed = parse_listing_slug(slug)
            if not parsed:
                continue
            self.labels[slug] = label
            topic, city, remote = parsed
            entry = self.topics.setdefault(topic, {"cities": set(), "remote": False, "remote_cities": set()})
            if remote and city:
                entry["remote_cities"].add(city)
            elif remote:
                entry["remote"] = True
            elif city:
                entry["cities"].add(city)
            else:
                self.topic_labels[topic] = label
        self._compact = {}
        for topic in self.topics:
            self._compact.setdefault(topic.replace("-", ""), []).append(topic)

    def has(self, slug):
        return slug in self.labels

    def weight(self, topic):
        """How many listing pages a topic has (16 for the big skills): the
        popularity proxy that ranks fuzzy matches."""
        entry = self.topics.get(topic)
        if not entry:
            return 0
        return 1 + len(entry["cities"]) + int(entry["remote"]) + len(entry["remote_cities"])

    def by_compact(self, compact):
        return self._compact.get(compact, [])

    def topic_label(self, topic):
        label = self.topic_labels.get(topic)
        if label:
            return label
        return " ".join(w.capitalize() for w in topic.split("-")) + " Jobs"


_catalogue = None


def catalogue(rows=None):
    """The JobCatalogue over `rows` (live) or the snapshot (cached)."""
    global _catalogue
    if rows is not None:
        return JobCatalogue(rows)
    with _lock:
        if _catalogue is None:
            _catalogue = JobCatalogue(snapshot()["jobs"])
        return _catalogue


def company_listing_labels():
    return {slug: label for slug, label in snapshot()["companies"]}


def salary_pages():
    """{(title_slug, location_slug): label}."""
    out = {}
    for key, label in snapshot()["salaries"]:
        title, _, location = key.partition("/")
        out[(title, location or "india")] = label
    return out


def salary_titles():
    """title slug -> display title ('python-developer' -> 'Python Developer')."""
    out = {}
    for (title, _location), label in salary_pages().items():
        match = re.match(r"Salary for (.+?) in ", label or "")
        out.setdefault(title, match.group(1) if match else " ".join(w.capitalize() for w in title.split("-")))
    return out


def job_description_slugs():
    return list(snapshot()["job_descriptions"])
