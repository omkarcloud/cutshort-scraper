"""Configuration for the Cutshort Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT             port the API listens on (default 8000)
    CUTSHORT_PROXY   proxy URL for every request, e.g. http://user:pass@host:port
                     (default: none — direct). Cutshort answered 40 parallel
                     requests from one IP without a single block, so you very
                     likely don't need this. Set it only if you start seeing
                     failures at high volume.
    MAX_RETRIES      attempts per request on a transport error or block
                     (default 3; the wait grows by 1 s per attempt)
    CUTSHORT_WORKERS parallel requests inside one call, e.g. the 10 jobs of
                     /jobs/batch (default 6)
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
CUTSHORT_MAX_ATTEMPTS = MAX_RETRIES

CUTSHORT_WORKERS = int(os.environ.get("CUTSHORT_WORKERS", "6"))

CUTSHORT_PROXY = os.environ.get("CUTSHORT_PROXY") or None


def cutshort_proxy(fallback=False):
    """The proxy for every Cutshort request (retries included): CUTSHORT_PROXY,
    or None for a direct connection."""
    return os.environ.get("CUTSHORT_PROXY") or None
