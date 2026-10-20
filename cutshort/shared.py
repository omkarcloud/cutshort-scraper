"""Value helpers shared by every Cutshort parser: safe nested access,
numbers, text, dates, site links and HTML descriptions. Pure functions, no
network; every helper tolerates None and junk.

The generic helpers (g / as_list / as_dict, num … iso_date, html_to_text)
have the same semantics as instahyre/shared.py and seek/shared.py; they
live here so the cutshort package stands alone (it ships as its own
open-source repo, which must not pull in other sites' modules)."""
import html as html_lib
import re
from datetime import datetime
from html.parser import HTMLParser

from cutshort import refdata

# ---- safe access ---------------------------------------------------------------------------

def g(obj, *path, default=None):
    """Safe nested get: g(d, "a", "b", 0) -> d["a"]["b"][0] or default."""
    for step in path:
        if isinstance(step, int):
            if not isinstance(obj, list) or not -len(obj) <= step < len(obj):
                return default
            obj = obj[step]
        else:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(step)
        if obj is None:
            return default
    return obj


def as_list(value):
    return value if isinstance(value, list) else []


def as_dict(value):
    return value if isinstance(value, dict) else {}


# ---- numbers -------------------------------------------------------------------------------

def num(value):
    """int / float / numeric string ('1,234.5') -> float; bool, junk, NaN -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None
    try:
        out = float(str(value).strip().replace(",", ""))
    except ValueError:
        return None
    return out if out == out else None


def to_int(value):
    out = num(value)
    return int(round(out)) if out is not None else None


def count(value):
    """A non-negative count; negatives -> 0."""
    out = to_int(value)
    if out is None:
        return None
    return out if out >= 0 else 0


def year(value):
    """A founding year: 4-digit int, else None (the site stores 0 for unknown)."""
    out = to_int(value)
    return out if out and 1000 <= out <= 2100 else None


def lakhs(value):
    """An annual amount in INR -> lakhs (1 lakh = 100,000) rounded to 2 places."""
    out = num(value)
    return round(out / refdata.LAKH, 2) if out is not None else None


# ---- text ----------------------------------------------------------------------------------

def text(value):
    """Whitespace-collapsed, HTML-unescaped string; '' -> None."""
    if value is None or isinstance(value, bool):
        return None
    out = " ".join(html_lib.unescape(str(value)).replace("\xa0", " ").split())
    return out or None


def multiline(value):
    """Like text() but keeps line breaks (descriptions)."""
    if value is None:
        return None
    lines = [" ".join(line.split()) for line in html_lib.unescape(str(value)).replace("\xa0", " ").splitlines()]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out or None


def text_list(values):
    """A list of strings, trimmed, deduped, empties dropped."""
    out = []
    for value in as_list(values):
        item = text(value)
        if item and item not in out:
            out.append(item)
    return out


def slugify(value):
    """'Python Developer' -> 'python-developer'."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or None


def compact(value):
    """'React.js' -> 'reactjs' (the site's own topic slugs drop punctuation)."""
    out = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    return out or None


def title_from_slug(value):
    """'ux-design' -> 'Ux Design' (a fallback label)."""
    value = text(value)
    if not value:
        return None
    return " ".join(w.capitalize() for w in value.split("-"))


def iso_date(value):
    """'2026-10-12T…' / '2026-10-12' -> 'YYYY-MM-DD'."""
    value = text(value)
    if not value:
        return None
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        return "-".join(match.groups())
    for fmt in ("%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def iso_datetime(value):
    """'2026-10-12T07:16:56.037Z' -> '2026-10-12T07:16:56Z' (UTC, no millis)."""
    value = text(value)
    if not value:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", value)
    if match:
        return f"{match.group(1)}T{match.group(2)}Z"
    return None


# ---- links -------------------------------------------------------------------------------

def link(path):
    """A site-relative path (or absolute URL) -> absolute https link; '' / None -> None."""
    path = text(path) if isinstance(path, str) else None
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith("//"):
        return "https:" + path
    return f"{refdata.BASE_URL}/{path.lstrip('/')}"


def external_link(value):
    """An off-site link as the employer typed it ('https://acme.com',
    'www.acme.com/', 'acme.com') -> absolute link; never rebased onto
    cutshort.io like link() does; junk with no domain -> None."""
    value = text(value) if isinstance(value, str) else None
    if not value:
        return None
    if value.lower().startswith(("http://", "https://")):
        return value
    if value.startswith("/"):
        return link(value)
    return f"https://{value}" if re.match(r"[^/\s]+\.[a-z]{2,}", value, re.I) else None


def company_link(alias):
    return f"{refdata.BASE_URL}/company/{alias}" if alias else None


def listing_link(slug):
    return f"{refdata.BASE_URL}/jobs/{slug}" if slug else None


def job_short_id(value):
    """'https://cutshort.io/job/Full-Stack-Engineer-Provenir-I1i8FXO2' /
    'Full-Stack-Engineer-Provenir-I1i8FXO2' -> 'I1i8FXO2' (the 8-char id the
    backend resolves)."""
    value = text(value)
    if not value:
        return None
    tail = value.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    match = re.search(r"([A-Za-z0-9_]{8})$", tail)
    return match.group(1) if match else None


def is_remote_city(name):
    return (text(name) or "").lower() in ("remote only", "remote", "work from home", "anywhere")


# ---- HTML -> text ------------------------------------------------------------------------------------

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
               "section", "article", "header", "footer", "blockquote", "pre", "hr", "dd", "dt", "dl"}
_SKIP_TAGS = {"script", "style", "noscript", "template", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in ("li", "br"):
            return
        elif tag in ("ul", "ol"):
            self.parts.append("\n\n")      # a list ends its paragraph
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(value):
    """An HTML fragment -> readable plain text: block elements become line
    breaks, list items get a dash, runs of blank lines collapse."""
    value = value if isinstance(value, str) else None
    if not value:
        return None
    if "<" not in value:
        return multiline(value)
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return multiline(re.sub(r"<[^>]+>", " ", value))
    raw = "".join(parser.parts).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in raw.splitlines()]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\n\n(- )", r"\n\1", out).strip()   # list items stay tight
    return out or None


def html_fragment(value):
    """Rich text as the site stores it, trimmed; '' / '<p><br /></p>' -> None."""
    value = value if isinstance(value, str) else None
    if not value or not value.strip():
        return None
    if not html_to_text(value):
        return None
    return value.strip()
