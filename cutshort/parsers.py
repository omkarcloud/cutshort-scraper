"""Raw Cutshort payloads -> the API's response shapes. Pure functions over
the site's backend JSON (fetch.py) and the __NEXT_DATA__ of its salary
pages; every parser tolerates a partial record.

Dropped on purpose: `seoData` (page titles, JSON-LD and canonical links —
every fact in them is on the record itself), `pageContext` (the
candidate/employer SEO toggle), `authApplyUrl` / `isJobSaved` (the logged-in
apply flow), the `*Vanity` salary and experience copies (rounded display
values of the real band), `ogImage` / `coverPictureURL` (the site's stock
share images), `sectionsEnabled` (which profile sections the employer
toggled on — the sections themselves are returned, empty when off),
`allUsersOnNonPaidPlan` / `companyLevelActivityExistsPreviously` (billing
flags), `USMReview` (internal moderation status), `uploadedImageIds` /
`approvedEmployers` / `isASibling` / `isADuplicate` / `collections` (Algolia
record bookkeeping), `_highlightResult` (search highlighting), `caseStudy` /
`testimonials` (the site's own marketing on description pages),
`breadcrumbs` (navigation), `menu_has_sub_cat` (layout)."""
import json
import re
from math import ceil

from cutshort import refdata
from cutshort import shared as S
from cutshort.shared import as_dict, as_list, g

CURRENCY_SYMBOLS = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP", "$CA": "CAD", "A$": "AUD", "S$": "SGD",
                    "AED": "AED"}


# ---- salary / experience bands ---------------------------------------------------------------------

def _amount(value, unit):
    out = S.num(value)
    if out is None:
        return None
    unit = (unit or "").lower()
    if unit in ("l", "lakh", "lakhs", "lac", "lacs"):
        out *= refdata.LAKH
    elif unit in ("k",):
        out *= 1_000
    elif unit in ("cr", "crore", "crores"):
        out *= 100 * refdata.LAKH
    elif unit in ("m", "mn"):
        out *= 1_000_000
    return out


_MONEY_RE = re.compile(r"([₹$€£]|[A-Z]{3}|A\$|S\$|\$CA)?\s*([\d.,]+)\s*(L|K|Cr|M|lakhs?|lacs?|crores?)?", re.I)


def salary_text(value):
    """'₹20L - ₹40L / yr' / 'Upto ₹12L / yr' / '$80K - $120K / yr' ->
    {currency, min, max, per, text}; None when there is no figure."""
    raw = S.text(value)
    if not raw:
        return None
    matches = [m for m in _MONEY_RE.finditer(raw) if m.group(2) and re.search(r"\d", m.group(2))]
    if not matches:
        return None
    currency = None
    for m in matches:
        sym = (m.group(1) or "").strip()
        if sym:
            currency = CURRENCY_SYMBOLS.get(sym) or (sym.upper() if sym.isalpha() else None)
            break
    amounts = [_amount(m.group(2), m.group(3)) for m in matches]
    amounts = [a for a in amounts if a is not None]
    if not amounts:
        return None
    upto = raw.lower().startswith(("upto", "up to"))
    per = "year" if re.search(r"/\s*(yr|year|annum|pa)\b", raw, re.I) else ("month" if re.search(r"/\s*(mo|month)\b", raw, re.I) else None)
    low = None if upto and len(amounts) == 1 else amounts[0]
    high = amounts[-1] if len(amounts) > 1 or upto else (amounts[0] if len(amounts) == 1 else None)
    return {"currency": currency or refdata.DEFAULT_CURRENCY, "min": low, "max": high, "per": per, "text": raw}


def _positive(*values):
    """The first value that is a positive number (the site stores 0 for 'unset')."""
    for value in values:
        out = S.num(value)
        if out is not None and out > 0:
            return out
    return None


_ESOP_RE = re.compile(r"\(?\s*ESOPs?\s+available\s*\)?", re.I)


def salary_band(raw, text=None):
    """The card's numeric salaryRange ({currency, min, max} + *Vanity copies)
    -> {currency, min, max, min_lakhs, max_lakhs, per, has_esop, text}; the
    detail page carries only the text ('₹20L - ₹40L / yr (ESOP available)'),
    parsed with salary_text. A band of zeros ('₹0L / yr') is undisclosed:
    min / max null. None when there is neither a figure nor a text."""
    display = S.text(text) if text is not None else (S.text(raw) if isinstance(raw, str) else None)
    has_esop = bool(display and _ESOP_RE.search(display))
    figures = _ESOP_RE.sub("", display).strip() if display else None
    if isinstance(raw, dict) and raw:
        currency = S.text(raw.get("currency")) or refdata.DEFAULT_CURRENCY
        # The site shows the *Vanity band (its rounded public figures, the ones
        # in the text and on the job page) when it is set; a 0 there means
        # unset, so fall back to what the employer typed (userMin / min).
        low = _positive(raw.get("minVanity"), raw.get("userMin"), raw.get("min"))
        high = _positive(raw.get("maxVanity"), raw.get("userMax"), raw.get("max"))
        currency, per = currency, "year"
    else:
        parsed = salary_text(figures) if figures else None
        if parsed is None and not display:
            return None
        parsed = parsed or {"currency": refdata.DEFAULT_CURRENCY, "min": None, "max": None, "per": "year"}
        currency, per = parsed["currency"], parsed.get("per") or "year"
        low = parsed["min"] if parsed["min"] else None
        high = parsed["max"] if parsed["max"] else None
    if low is not None and high is not None and low > high:
        low, high = high, low
    lakhs = currency == "INR"
    return {
        "currency": currency,
        "min": low,
        "max": high,
        "min_lakhs": S.lakhs(low) if lakhs else None,
        "max_lakhs": S.lakhs(high) if lakhs else None,
        "per": per,
        "has_esop": has_esop,
        "text": display,
    }


def experience_band(raw, text=None):
    raw = as_dict(raw)
    low, high = S.num(raw.get("min")), S.num(raw.get("max"))
    if low is None and high is None:
        match = re.search(r"(\d+)\s*-\s*(\d+)\s*years?", S.text(text) or "")
        if match:
            low, high = float(match.group(1)), float(match.group(2))
        elif text is None:
            return None
    return {"min_years": low, "max_years": high, "text": S.text(text)}


def remote_policy(code):
    return refdata.REMOTE_TYPES.get(S.text(code) or "")


def skills(raw):
    """allSkillsObj {code: name} (ordered as the employer listed them) ->
    [{code, name, icon}]; falls back to the bare allSkills names."""
    obj = as_dict(raw.get("allSkillsObj"))
    out = []
    if obj:
        for code, name in obj.items():
            name = S.text(name)
            if name:
                out.append({"code": S.text(code), "name": name})
    else:
        out = [{"code": None, "name": name} for name in S.text_list(raw.get("allSkills"))]
    return out


def role_types(raw):
    return [refdata.ROLE_TYPES.get(r, r) for r in S.text_list(raw)]


def locations_of(raw):
    """A card's locations list or a detail page's 'Bengaluru (Bangalore), Pune'
    text -> {names, is_remote}."""
    names = S.text_list(raw) if isinstance(raw, list) else [n for n in S.text_list((S.text(raw) or "").split(","))]
    remote = any(S.is_remote_city(n) for n in names)
    return {"names": [n for n in names if not S.is_remote_city(n)], "is_remote": remote}


_LINK_ORDER = ("website", "about", "blog", "linkedin", "twitter", "facebook", "instagram", "youtube", "youtube_video",
               "team", "ambitionbox", "glassdoor", "crunchbase", "github", "angellist")


def _snake(key):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def _real_link(value):
    """A profile link worth returning: not a bare domain or a bare
    'youtube.com/watch' the site keeps as a placeholder."""
    value = S.text(value)
    if not value:
        return None
    url = S.external_link(value)
    match = re.match(r"https?://[^/]+(/.*)?$", url or "")
    path = (match.group(1) or "") if match else ""
    if not path.strip("/") or path.rstrip("/") == "/watch":
        bare = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
        host = bare.group(1).lower() if bare else ""
        if host in ("linkedin.com", "youtube.com", "facebook.com", "twitter.com", "instagram.com", "x.com",
                    "glassdoor.com", "ambitionbox.com", "crunchbase.com", "github.com"):
            return None
    return url


def links_of(raw):
    """Every link the company set (website, about / careers page, blog,
    socials, AmbitionBox, team page, intro video), snake_cased, null when
    missing; `articles` the press links."""
    raw = as_dict(raw)
    out = {key: None for key in _LINK_ORDER}
    for key, value in raw.items():
        if key == "articles":
            continue
        name = _snake(str(key))
        if isinstance(value, str) or value is None:
            out[name] = _real_link(value)
    articles = []
    for item in as_list(raw.get("articles")):
        url = S.external_link(item.get("link") or item.get("url")) if isinstance(item, dict) else S.external_link(item)
        if url:
            articles.append(url)
    out["articles"] = articles
    return out


# ---- companies ----------------------------------------------------------------------------------------

def _code_or_text(value, table):
    """The site stores company type / stage / size as codes on some records
    and as labels on others; return the label either way."""
    text = S.text(value)
    if text is None:
        return None
    return table.get(text.lower(), table.get(text, text))


def company_type(value):
    return _code_or_text(value, refdata.COMPANY_TYPES)


def company_stage(value):
    return _code_or_text(value, refdata.COMPANY_STAGES)


def company_size(value, new_size=None):
    code = S.text(new_size)
    if code and code in refdata.COMPANY_SIZES:
        return refdata.COMPANY_SIZES[code]
    return _code_or_text(value, refdata.COMPANY_SIZES)


def faqs(raw):
    out = []
    for row in as_list(raw):
        row = as_dict(row)
        question = S.text(row.get("question"))
        if question:
            out.append({"question": question, "answer_html": S.html_fragment(row.get("answer")),
                        "answer": S.html_to_text(row.get("answer"))})
    return out


def team_members(raw):
    out = []
    for row in as_list(raw):
        row = as_dict(row)
        name = S.text(row.get("name"))
        if name:
            out.append({"id": S.text(row.get("userId") or row.get("_id")), "name": name,
                        "title": S.text(row.get("title") or row.get("headline")),
                        "linkedin": S.external_link(row.get("linkedIn")) if S.text(row.get("linkedIn")) not in (None, "https://linkedin.com") else None,
                        "photo": S.link(row.get("profilePicture"))})
    return out


def company_card(raw):
    """The company embedded on a job (companyDetails) -> the card."""
    raw = as_dict(raw)
    if not raw:
        return None
    alias = S.text(raw.get("alias"))
    return {
        "id": S.text(raw.get("_id")),
        "name": S.text(raw.get("name")),
        "alias": alias,
        "link": S.company_link(alias),
        "logo": S.link(raw.get("logo")),
        "type": company_type(raw.get("type")),
        "size": company_size(raw.get("size"), raw.get("newSize")),
        "stage": company_stage(raw.get("stage")),
        "funding": refdata.COMPANY_FUNDINGS.get(S.text(raw.get("funding")) or ""),
        "founded_year": S.year(raw.get("founded")),
        "followers_count": S.count(raw.get("followersCount")),
        "is_hiring_for_client": bool(raw.get("hiringForClient")),
        "website": S.external_link(g(raw, "links", "website")),
        "linkedin": S.external_link(g(raw, "links", "linkedin")),
        "description": S.html_to_text(raw.get("sanitizedDescription") or raw.get("description")),
        "description_html": S.html_fragment(raw.get("sanitizedDescription") or raw.get("description")),
        "faqs": faqs(raw.get("companyFAQs")),
        "tech_stack": S.text_list(raw.get("techStack")),
        "team": team_members(raw.get("highlightTeamMembers")),
        "photos": [S.link(p) for p in S.text_list(raw.get("photos"))],
        "products": [S.text(p) if isinstance(p, str) else p for p in as_list(raw.get("productShowcase"))],
    }


def company_summary(raw):
    """A card from a directory / similar-companies row."""
    raw = as_dict(raw)
    alias = S.text(raw.get("alias"))
    return {
        "id": S.text(raw.get("_id")),
        "name": S.text(raw.get("name")),
        "alias": alias,
        "link": S.company_link(alias),
        "logo": S.link(raw.get("logo")),
        "website": S.external_link(raw.get("websiteLink")),
        "type": company_type(raw.get("type")),
        "size": company_size(raw.get("size")),
        "stage": company_stage(raw.get("stage")),
        "founded_year": S.year(raw.get("founded")),
        "jobs_count": S.count(raw.get("jobCount")),
        "description": S.html_to_text(raw.get("description")),
    }


def company_profile(raw_page, alias=None):
    """The company page -> profile + similar companies + its jobs page."""
    page = as_dict(as_dict(raw_page).get("pageData"))
    raw = as_dict(page.get("company"))
    alias = S.text(raw.get("alias")) or alias
    jobs_block = as_dict(page.get("companyJobs"))
    total_jobs = S.count(raw.get("totalJobsOfCompany"))
    return {
        "id": S.text(raw.get("_id")),
        "name": S.text(raw.get("name")),
        "alias": alias,
        "link": S.company_link(alias),
        "logo": S.link(raw.get("logo")),
        "type": company_type(raw.get("type")),
        "size": company_size(raw.get("size"), raw.get("newSize")),
        "stage": company_stage(raw.get("stage")),
        "funding": refdata.COMPANY_FUNDINGS.get(S.text(raw.get("funding")) or ""),
        "founded_year": S.year(raw.get("founded")),
        "domains": S.text_list(raw.get("domains")),
        "followers_count": S.count(raw.get("followersCount")),
        "jobs_count": total_jobs,
        "is_hiring_for_client": bool(raw.get("hiringForClient")),
        "description": S.html_to_text(raw.get("sanitizedDescription") or raw.get("description")),
        "description_html": S.html_fragment(raw.get("sanitizedDescription") or raw.get("description")),
        "links": links_of(raw.get("links")),
        "location_preferences": S.text_list(raw.get("locationPreferences")),
        "typical_3yr_developer_salary": salary_band(raw.get("typical3yrDevSalary")) if as_dict(raw.get("typical3yrDevSalary")) else None,
        "faqs": faqs(raw.get("companyFAQs")),
        "tech_stack": S.text_list(raw.get("techStack")),
        "team": team_members(raw.get("highlightTeamMembers")),
        "hiring_team": team_members(raw.get("hiringEmployers")),
        "photos": [S.link(p) for p in S.text_list(raw.get("photos") or raw.get("companyPhotos"))],
        "products": [S.text(p) if isinstance(p, str) else p for p in as_list(raw.get("productShowcase"))],
        "jobs": [job_card(j) for j in as_list(jobs_block.get("jobs")) if isinstance(j, dict)],
        "jobs_pagination": {"page": S.to_int(jobs_block.get("page")) or 1,
                            "items_per_page": refdata.COMPANY_JOBS_PAGE_SIZE,
                            "total_pages": S.count(jobs_block.get("totalPages")) or 0,
                            "total_count": total_jobs},
        "similar_companies": [company_summary(c) for c in as_list(page.get("similarCompanies")) if isinstance(c, dict)],
    }


# ---- jobs --------------------------------------------------------------------------------------------

def _posted(raw):
    fact = as_dict(raw.get("jobFactSummary"))
    stamp = fact.get("postedDate") or raw.get("hiringIntentShownOn")
    return S.iso_datetime(stamp), S.iso_date(stamp)


def recruiter(raw):
    raw = as_dict(raw)
    if not raw:
        return None
    return {"id": S.text(raw.get("_id")), "name": S.text(raw.get("name")), "photo": S.link(raw.get("profilePicture"))}


def related_links(raw):
    out = []
    for row in as_list(raw):
        row = as_dict(row)
        href = S.text(row.get("href") or row.get("url"))
        if href:
            out.append({"label": S.text(row.get("label") or row.get("name")), "link": S.link(href),
                        "slug": href.rstrip("/").rsplit("/", 1)[-1]})
    return out


def _job_core(raw):
    raw = as_dict(raw)
    fact = as_dict(raw.get("jobFactSummary"))
    posted_at, posted_on = _posted(raw)
    link = S.link(raw.get("publicUrl"))
    salary = salary_band(raw.get("salaryRange"), raw.get("salaryRangeText") or fact.get("salary"))
    locs = locations_of(raw.get("locations") if isinstance(raw.get("locations"), list) else (raw.get("locationsText") or fact.get("locations")))
    policy = remote_policy(raw.get("remoteType"))
    return {
        "id": S.job_short_id(link),
        "record_id": S.text(raw.get("_id")),
        "title": S.text(raw.get("headline")),
        "link": link,
        "company": None,                              # filled by the caller
        "locations": locs["names"],
        "is_remote": policy == "remote" or (locs["is_remote"] and policy is None),
        "remote_policy": policy,
        "role_types": role_types(raw.get("roleTypes")),
        "is_internship": "internship" in role_types(raw.get("roleTypes")),
        "experience": experience_band(raw.get("expRange"), fact.get("experience")),
        "salary": salary,
        "skills": skills(raw),
        "is_hiring_for_client": bool(raw.get("hiringForClient")),
        "posted_at": posted_at,
        "posted_on": posted_on,
    }


def job_card(raw):
    """A listing / similar / company-page card (the site ships the full
    description and company on cards too)."""
    raw = as_dict(raw)
    out = _job_core(raw)
    company = company_card(raw.get("companyDetails"))
    poster = _company_ref(raw.get("companyId"))
    if company is None and poster:
        company = poster
    out["company"] = _company_brief(company)
    out["recruiting_company"] = _recruiting_company(out, poster)
    out["description"] = S.html_to_text(raw.get("sanitizedComment"))
    out["description_html"] = S.html_fragment(raw.get("sanitizedComment"))
    out["recruiter"] = recruiter(raw.get("createdBy"))
    out["related_listings"] = related_links(raw.get("relatedHubLinks"))
    return out


def _company_ref(raw):
    """The companyId stub on a card ({_id, name, alias}) -> a minimal card."""
    ref = as_dict(raw)
    if not ref:
        return None
    alias = S.text(ref.get("alias"))
    return {"id": S.text(ref.get("_id")), "name": S.text(ref.get("name")), "alias": alias,
            "link": S.company_link(alias), "logo": S.link(ref.get("logo"))}


def _recruiting_company(job, poster):
    """On a job posted for a client, `company` is the client as the site
    shows it (often masked: 'MNC', 'Technology Industry') and the posting
    agency / consultancy is companyId; surface it as recruiting_company."""
    if not job.get("is_hiring_for_client") or not poster:
        return None
    company = job.get("company") or {}
    if poster.get("alias") and poster.get("alias") == company.get("alias"):
        return None
    return {"id": poster.get("id"), "name": poster.get("name"), "alias": poster.get("alias"), "link": poster.get("link")}


def _company_brief(company):
    if not company:
        return None
    keys = ("id", "name", "alias", "link", "logo", "type", "size", "stage", "funding", "founded_year",
            "followers_count", "is_hiring_for_client", "website", "linkedin")
    return {k: company.get(k) for k in keys}


def job_details(raw_page, similar=None):
    """The job page -> the full job with its company profile card."""
    page = as_dict(as_dict(raw_page).get("pageData"))
    out = _job_core(page)
    match = as_dict(page.get("matchPreferences"))
    client = as_dict(page.get("clientCompanyId"))
    out.update({
        "is_live": page.get("jobValid") if isinstance(page.get("jobValid"), bool) else None,
        "shows_only_max_salary": bool(page.get("showOnlyMaxSalary")),
        "category": S.text(match.get("tagCategory")),
        "tags": S.text_list(match.get("tags")),
        "description": S.html_to_text(page.get("sanitizedComment")),
        "description_html": S.html_fragment(page.get("sanitizedComment")),
        "recruiter": recruiter(page.get("createdBy")),
        "company": company_card(page.get("companyDetails")),
        "recruiting_company": _recruiting_company({"is_hiring_for_client": out["is_hiring_for_client"],
                                                   "company": company_card(page.get("companyDetails"))},
                                                  _company_ref(page.get("companyId"))),
        "client_company": {"id": S.text(client.get("_id")), "name": S.text(client.get("name")),
                           "alias": S.text(client.get("alias"))} if client else None,
        "related_listings": related_links(page.get("relatedHubLinks")),
        "similar_jobs": [job_card(j) for j in as_list(similar) if isinstance(j, dict)] if similar is not None else None,
    })
    return out


# ---- listings -----------------------------------------------------------------------------------------

def side_links(raw):
    """The listing page's link menus -> [{title, links: [{label, link, slug}]}]
    (sub-menus flattened under their group name)."""
    out = []
    for menu in as_list(raw):
        menu = as_dict(menu)
        links = []
        for item in as_list(menu.get("menu_items")):
            item = as_dict(item)
            if as_list(item.get("sub_items")):
                for sub in as_list(item.get("sub_items")):
                    sub = as_dict(sub)
                    if S.text(sub.get("url")):
                        links.append({"group": S.text(item.get("name")), "label": S.text(sub.get("name")),
                                      "link": S.link(sub.get("url")),
                                      "slug": S.text(sub.get("url")).rstrip("/").rsplit("/", 1)[-1]})
            elif S.text(item.get("url")):
                links.append({"group": None, "label": S.text(item.get("name")), "link": S.link(item.get("url")),
                              "slug": S.text(item.get("url")).rstrip("/").rsplit("/", 1)[-1]})
        if links:
            out.append({"title": S.text(menu.get("name_of_menu")), "links": links})
    return out


def listing_page(raw_page, slug, page):
    page_data = as_dict(as_dict(raw_page).get("pageData"))
    total = S.count(page_data.get("liveJobCount"))
    jobs = [job_card(j) for j in as_list(page_data.get("jobs")) if isinstance(j, dict)]
    pages = ceil(total / refdata.PAGE_SIZE) if total else (page if jobs else 0)
    return {
        "listing": {"slug": slug, "link": S.listing_link(slug), "title": S.text(page_data.get("title")),
                    "description": S.text(page_data.get("subTitle"))},
        "jobs": jobs,
        "related_listings": side_links(page_data.get("sideJobLinks")),
        "pagination": {"page": page, "items_per_page": refdata.PAGE_SIZE, "total_pages": pages, "total_count": total},
    }


def category_entry(raw, labels=None):
    raw = as_dict(raw)
    slug = S.text(raw.get("slug"))
    data = as_dict(raw.get("dataJSON"))
    parsed = refdata.parse_listing_slug(slug) if slug else None
    topic, city, remote = parsed if parsed else (None, None, None)
    return {
        "slug": slug,
        "title": S.text(data.get("h1") or data.get("pageTitle")) or (labels or {}).get(slug),
        "link": S.listing_link(slug),
        "topic": topic,
        "location": refdata.CITIES.get(city, (None,))[0] if city else None,
        "location_slug": city,
        "is_remote": bool(remote),
        "skill_codes": [c for c in str(data.get("skills") or "").split(",") if c],
        "tag": S.text(data.get("tag")),
        "category": S.text(data.get("tagCategory")),
    }


def categories_page(raw_page, page):
    page_data = as_dict(as_dict(raw_page).get("pageData"))
    entries = []
    for group in as_list(page_data.get("jobsList")):
        for row in as_list(as_dict(group).get("links")):
            if isinstance(row, dict):
                entries.append(category_entry(row))
    total = S.count(page_data.get("totalCategories"))
    return {
        "categories": entries,
        "featured": [category_entry(r) for r in as_list(page_data.get("topJobsList")) if isinstance(r, dict)],
        "pagination": {"page": S.to_int(page_data.get("page")) or page,
                       "items_per_page": S.to_int(page_data.get("pageSize")) or 15,
                       "total_pages": S.count(page_data.get("pageCount")) or 0, "total_count": total},
    }


def directory_page(raw_page, slug, page):
    page_data = as_dict(as_dict(raw_page).get("pageData"))
    companies = [company_summary(c) for c in as_list(page_data.get("companies")) if isinstance(c, dict)]
    return {
        "directory": {"slug": slug, "link": f"{refdata.BASE_URL}/companies/{slug}",
                      "title": S.text(page_data.get("h1") or page_data.get("title")),
                      "description": S.text(page_data.get("h2") or page_data.get("subTitle"))},
        "companies": companies,
        "related_directories": side_links(page_data.get("sideJobLinks")),
        "pagination": {"page": page, "items_per_page": refdata.DIRECTORY_PAGE_SIZE, "total_pages": None,
                       "total_count": None},
    }


def sitemap_catalogue(raw_page):
    """The sitemap payload -> {"jobs": [[slug, label]…], "companies": […],
    "salaries": [["<title>/<location>", label]…]} (the catalogue shape)."""
    page_data = as_dict(as_dict(raw_page).get("pageData"))
    sections = {as_dict(s).get("id"): as_dict(s) for s in as_list(page_data.get("sitemap"))}

    def rows(section, key="id"):
        out = {}
        for group in as_list(as_dict(sections.get(section)).get("value")):
            for entry in as_list(as_dict(group).get("value")):
                entry = as_dict(entry)
                ident = S.text(entry.get(key))
                if key == "url" and ident:
                    ident = ident.split("/salary/")[-1]
                if ident:
                    out[ident] = S.text(entry.get("label"))
        return sorted(out.items())
    return {"jobs": [list(r) for r in rows("job_listings")], "companies": [list(r) for r in rows("company_listings")],
            "salaries": [list(r) for r in rows("salary_pages", key="url")]}


# ---- job descriptions ------------------------------------------------------------------------------------

def job_description(raw_page, slug):
    page_data = as_dict(as_dict(raw_page).get("pageData"))
    related = []
    for row in as_list(page_data.get("relatedJobDesc")):
        row = as_dict(row)
        link = S.text(row.get("link"))
        related.append({"slug": link.rstrip("/").rsplit("/", 1)[-1] if link else None, "title": S.text(row.get("name")),
                        "link": S.link(link), "logo": S.link(row.get("logo"))})
    jobs_link = S.text(page_data.get("jobPageLink"))
    return {
        "slug": slug,
        "title": S.text(page_data.get("personaSingular")),
        "page_title": S.text(page_data.get("title")),
        "link": f"{refdata.BASE_URL}/job-description/{slug}",
        "summary": S.text(page_data.get("subText")),
        "description_markdown": S.multiline(page_data.get("jobDescription")),
        "logo": S.link(page_data.get("skillLogo")),
        "hero_image": S.link(page_data.get("heroImageLink")),
        "jobs_listing": {"slug": jobs_link.rstrip("/").rsplit("/", 1)[-1], "link": S.link(jobs_link)} if jobs_link else None,
        "related": related,
    }


# ---- salary pages --------------------------------------------------------------------------------------

def next_data(html):
    """The __NEXT_DATA__ JSON of a Next.js page, or None."""
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def _queries(data):
    out = {}
    for q in as_list(g(data, "props", "pageProps", "dehydratedState", "queries")):
        if isinstance(q, dict):
            value = as_dict(q.get("state")).get("data")
            out[json.dumps(q.get("queryKey"), sort_keys=True)] = value if isinstance(value, (dict, list)) else {}
    return out


def _query(queries, head):
    """The dehydrated query whose key starts with `head` (first match)."""
    for key, value in queries.items():
        parsed = json.loads(key)
        if isinstance(parsed, list) and parsed and parsed[0] == head:
            yield parsed, value


def salary_page(html, title, location):
    data = next_data(html)
    if not data:
        return None
    queries = _queries(data)
    main = next((v for _, v in _query(queries, "salaryPageData") if isinstance(v, dict)), None)
    if not main:
        return None
    page_data = as_dict(main.get("pageData"))
    query = as_dict(page_data.get("queryData"))
    result = as_dict(page_data.get("salariesResult"))
    loc = as_dict(query.get("locationDetails"))
    trends = {}
    for key, value in _query(queries, "analyticsData"):
        value = as_dict(value)
        context = as_dict(key[1] if len(key) > 1 else {}).get("context")
        block = as_dict(value.get("data"))
        rows = [{"slug": S.text(r.get("id")), "label": S.text(r.get("headline") or r.get("label")),
                 "lakhs_per_year": S.num(r.get("value"))} for r in as_list(block.get("value")) if isinstance(r, dict)]
        if context == "salary-trend-across-cities":
            trends["by_city"] = rows
        elif context == "salary-trend-across-roles":
            trends["by_role"] = rows
    related = []
    for _, value in _query(queries, "otherSalaryPageLinks"):
        value = as_dict(value)
        for row in as_list(value.get("results")):
            row = as_dict(row)
            related.append({"title": S.text(row.get("title")), "title_slug": S.text(row.get("titleSlug")),
                            "location": S.text(row.get("locationDisplayText")), "location_slug": S.text(row.get("locationSlug")),
                            "link": f"{refdata.BASE_URL}/salary/{S.text(row.get('slug'))}" if S.text(row.get("slug")) else None,
                            "median_lakhs_per_year": S.num(row.get("salary"))})

    def tier(key):
        row = as_dict(result.get(key))
        if not row:
            return None
        return {"lakhs_per_year": S.num(row.get("salary")), "label": S.text(row.get("title")),
                "note": S.text(row.get("helpText"))}
    return {
        "title": S.text(query.get("jobTitle")) or S.title_from_slug(title),
        "title_slug": S.text(query.get("slug")) or title,
        "location": S.text(loc.get("display_text")) or refdata.SALARY_LOCATIONS.get(location, (S.title_from_slug(location),))[0],
        "location_slug": S.text(loc.get("seoSlug")) or location,
        "is_remote": bool(query.get("remote")) or location == "remote",
        "link": f"{refdata.BASE_URL}/salary/{title}/{location}",
        "heading": S.text(page_data.get("pageHeading")),
        "currency": refdata.DEFAULT_CURRENCY,
        "experience_years": S.to_int(query.get("experience")),
        "category": S.text(query.get("tagCategory")),
        "tag": S.text(query.get("tag")),
        "percentiles": {"top_5_percent": tier("top5percent"), "top_10_percent": tier("top10percent"),
                        "top_20_percent": tier("top20percent")},
        "trends": {"by_city": trends.get("by_city", []), "by_role": trends.get("by_role", [])},
        "faqs": [{"question": S.text(f.get("question")), "answer": S.html_to_text(f.get("answer"))}
                 for f in as_list(page_data.get("faqs")) if isinstance(f, dict) and S.text(f.get("question"))],
        "related_pages": related,
    }


def salary_lists(html):
    """The salary page's own location and role pickers."""
    data = next_data(html)
    queries = _queries(data) if data else {}
    locations, roles = [], []
    for key, value in _query(queries, "salarypage"):
        if key[1:] == ["locationList"]:
            value = as_dict(value)
            locations = [{"slug": S.text(r.get("seoSlug")), "name": S.text(r.get("display_text")),
                          "site_name": S.text(r.get("save_text"))} for r in as_list(value.get("locationsList")) if isinstance(r, dict)]
        elif key[1:] == ["salaryTagsData"]:
            for cat in as_list(value if isinstance(value, list) else []):
                cat = as_dict(cat)
                roles.append({"category": S.text(cat.get("_id")), "label": S.text(cat.get("label")),
                              "roles": [{"tag": S.text(t.get("_id")), "label": S.text(t.get("label")),
                                         "title": S.text(t.get("headline"))} for t in as_list(cat.get("tags")) if isinstance(t, dict)]})
    return {"locations": locations, "role_categories": roles}


# ---- Algolia suggestions ------------------------------------------------------------------------------------

def skill_suggestion(hit):
    hit = as_dict(hit)
    return {"code": S.text(hit.get("code") or hit.get("objectID")), "name": S.text(hit.get("name")),
            "alternate_names": S.text_list(hit.get("alias")), "icon": S.link(hit.get("icon")),
            "profiles_count": S.count(hit.get("refcount"))}


def company_suggestion(hit):
    hit = as_dict(hit)
    alias = S.text(hit.get("alias"))
    size = hit.get("size")
    return {"id": S.text(hit.get("objectID")), "name": S.text(hit.get("name")), "alias": alias,
            "link": S.company_link(alias), "logo": S.link(hit.get("logo")),
            "website": S.external_link(g(hit, "links", "website")),
            "type": company_type(hit.get("type")),
            "size": refdata.ALGOLIA_COMPANY_SIZES.get(S.to_int(size)) if isinstance(size, (int, float)) else company_size(size),
            "funding": refdata.COMPANY_FUNDINGS.get(S.text(hit.get("funding")) or ""),
            "founded_year": S.year(hit.get("founded")), "is_claimed": bool(hit.get("successfullyClaimed")),
            "profiles_count": S.count(hit.get("refcount")), "description": S.text(hit.get("description"))}


def title_suggestion(hit):
    hit = as_dict(hit)
    return {"id": S.text(hit.get("objectID")), "name": S.text(hit.get("name")),
            "category": S.text(hit.get("defaulMatchCategory")), "tags": S.text_list(hit.get("defaultTags")),
            "skill_codes": S.text_list(hit.get("skills")), "key_skill_codes": S.text_list(hit.get("mostImportantskills"))}


def location_suggestion(hit):
    hit = as_dict(hit)
    return {"code": S.text(hit.get("code") or hit.get("objectID")), "name": S.text(hit.get("name")),
            "country": S.text(hit.get("country")), "profiles_count": S.count(hit.get("refcount"))}
