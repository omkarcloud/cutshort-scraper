"""Marshmallow request schemas for every /cutshort/* route.

Generic fields live in the shared top-level schema_fields.py; this module
adds the Cutshort resolvers (refs.py). Every schema's load() output is the
kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrLinkField convention, never a
sibling `url`/`id` pair): `job` takes a job id (the 8 characters that end
every job slug, or the 24-hex record id), a slug or any job link; `company`
a page alias, a company link or a company name; `query` (job search) a
skill / role / topic, a listing slug or a listing link; `location` one of
the 14 cities under any of its spellings; `category` (directories) a
directory slug or link; `title` (salaries, job descriptions) a role slug,
name or page link.
"""
from marshmallow import ValidationError, fields, validate

from schema_fields import BaseSchema, ChoiceField, CommaListField, Flag, PageField, QueryField, RefField, StrippedString
from cutshort import refdata, refs


def _max_length(n):
    """validate.Length(max=n) that tolerates the None StrippedString returns
    for an empty value (marshmallow runs validators on it; len(None) is a 500)."""
    def check(value):
        if value is not None and len(value) > n:
            raise ValidationError(f"Longer than maximum length {n}.")
    return check


class _OptionalRef(RefField):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        super().__init__(**kwargs)


class JobField(RefField):
    resolver = staticmethod(refs.resolve_job)


class JobListField(RefField):
    resolver = staticmethod(refs.resolve_jobs)


class CompanyField(RefField):
    resolver = staticmethod(refs.resolve_company)


class ListingQueryField(_OptionalRef):
    resolver = staticmethod(refs.resolve_query)


class LocationField(_OptionalRef):
    resolver = staticmethod(refs.resolve_location)


class CategoryField(_OptionalRef):
    resolver = staticmethod(refs.resolve_category)


class SalaryTitleField(RefField):
    resolver = staticmethod(refs.resolve_salary_title)


class SalaryLocationField(_OptionalRef):
    resolver = staticmethod(refs.resolve_salary_location)


class JobDescriptionField(RefField):
    resolver = staticmethod(refs.resolve_job_description)


class ExperienceYearsField(fields.Integer):
    """Years of experience the candidate has: keeps the jobs whose band
    admits it (0 = jobs open to freshers)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=0, max=50))
        super().__init__(strict=False, **kwargs)


class LakhsField(fields.Float):
    """An annual INR amount in lakhs (1 lakh = 100,000; 12 = ₹12,00,000)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=0, max=10_000))
        super().__init__(**kwargs)


class LimitField(fields.Integer):
    def __init__(self, default=10, max_size=50, **kwargs):
        kwargs.setdefault("load_default", default)
        kwargs.setdefault("validate", validate.Range(min=1, max=max_size))
        super().__init__(strict=False, **kwargs)


# ---- jobs ----------------------------------------------------------------------------------------------------

class JobSearchSchema(BaseSchema):
    query = ListingQueryField(validate=_max_length(200))
    location = LocationField()
    remote = Flag()
    page = PageField(max_page=refdata.MAX_PAGE)
    experience_years = ExperienceYearsField()
    min_salary_lakhs = LakhsField()
    max_salary_lakhs = LakhsField()
    role_type = ChoiceField(list(refdata.ROLE_TYPE_FILTERS))
    company_type = ChoiceField(list(refdata.COMPANY_TYPE_FILTERS))
    remote_policy = ChoiceField(list(refdata.REMOTE_FILTERS))
    posted_within_days = fields.Integer(load_default=None, strict=False, validate=validate.Range(min=1, max=3650))
    skill = CommaListField(upper=False, max_items=10)


class JobSchema(BaseSchema):
    job = JobField()
    include_similar = Flag(load_default=False)


class JobBatchSchema(BaseSchema):
    jobs = JobListField()
    include_similar = Flag(load_default=False)


class SimilarJobsSchema(BaseSchema):
    job = JobField()


class CategoriesSchema(BaseSchema):
    query = ListingQueryField(validate=_max_length(200))
    location = LocationField()
    remote = Flag()
    page = PageField(max_page=1000)


# ---- companies ----------------------------------------------------------------------------------------------------

class CompanySchema(BaseSchema):
    company = CompanyField()
    page = PageField(max_page=refdata.MAX_PAGE)


class CompanyJobsSchema(BaseSchema):
    company = CompanyField()
    page = PageField(max_page=refdata.MAX_PAGE)


class CompanySearchSchema(BaseSchema):
    query = QueryField(max_length=100)
    limit = LimitField()


class DirectorySchema(BaseSchema):
    category = CategoryField()
    location = LocationField()
    page = PageField(max_page=refdata.MAX_PAGE)


class DirectoryCategoriesSchema(BaseSchema):
    location = LocationField()


# ---- salaries / content ----------------------------------------------------------------------------------------

class SalarySchema(BaseSchema):
    title = SalaryTitleField()
    location = SalaryLocationField()


class SalaryTitlesSchema(BaseSchema):
    location = SalaryLocationField()


class JobDescriptionSchema(BaseSchema):
    title = JobDescriptionField()


# ---- lookups ------------------------------------------------------------------------------------------------------------

class AutocompleteSchema(BaseSchema):
    query = QueryField(max_length=100)
    type = ChoiceField(list(refdata.ALGOLIA_INDICES), load_default="skills")
    limit = LimitField()


class EmptySchema(BaseSchema):
    pass
