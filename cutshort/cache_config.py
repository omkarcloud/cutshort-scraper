"""Cache TTL per /cutshort/* endpoint (cache.py, keyed on the validated
params — marshmallow fills the defaults, so an omitted param and its default
share a row).

Cutshort's own Cloudflare edge serves a listing page for 4 hours, so a
shorter TTL buys nothing; one job changes rarely once posted; company
pages move daily at most; the catalogue (listing slugs, directories,
salary pages) changes over weeks; salary pages are recomputed monthly."""
from datetime import timedelta

# --- raw upstream payloads shared by several routes (fetch.shared_raw) ----------
SITEMAP_RAW_CACHE = timedelta(days=1)        # the listing catalogue with labels
COMPANY_ALIAS_CACHE = timedelta(days=30)     # company name -> alias (never changes)

# --- jobs -----------------------------------------------------------------------------
SEARCH_CACHE = timedelta(hours=4)
JOB_CACHE = timedelta(hours=6)
SIMILAR_CACHE = timedelta(hours=6)
CATEGORIES_CACHE = timedelta(days=1)

# --- companies ----------------------------------------------------------------------------
COMPANY_CACHE = timedelta(days=1)
COMPANY_JOBS_CACHE = timedelta(hours=4)
DIRECTORY_CACHE = timedelta(days=1)
COMPANY_SEARCH_CACHE = timedelta(days=1)

# --- salaries / content ----------------------------------------------------------------------
SALARY_CACHE = timedelta(days=7)
JOB_DESCRIPTION_CACHE = timedelta(days=7)

# --- lookups ------------------------------------------------------------------------------
LOOKUPS_CACHE = timedelta(days=1)
AUTOCOMPLETE_CACHE = timedelta(days=7)
