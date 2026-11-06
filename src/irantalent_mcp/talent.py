"""IranTalent tools: job search and details, company directory, company profile, employee reviews, filter lookups."""

from __future__ import annotations

import asyncio
import html
import re
from typing import Annotated, Any, Literal

from pydantic import Field

from .http import SITE, ApiError, fetch
from .registry import tool
from .salary import salary_lookup

Page = Annotated[int, Field(description="1-based; 30 per page.", ge=1, le=500)]
CompanyId = Annotated[
    str,
    Field(
        description="Company UUID from it_search_jobs, it_companies or it_top_companies.",
        pattern=r"^[0-9a-fA-F-]{36}$",
    ),
]

LOOKUPS = {  # kind -> lookup id on api.irantalent.com
    "categories": 42,
    "industries": 9,
    "seniority": 10,
    "employment": 17,
    "company_size": 7,
}
WORK_TYPES = [
    {"slug": "on_site", "name": "On-site", "name_fa": "حضوری"},
    {"slug": "remote", "name": "Remote", "name_fa": "دورکاری"},
    {"slug": "hybrid", "name": "Hybrid", "name_fa": "ترکیبی"},
]
RATES = [
    "culture_and_value_rate",
    "salary_and_benefit_rate",
    "career_opportunity_rate",
    "learning_opportunity_rate",
    "work_life_balance_rate",
    "senior_management_rate",
]


def _text(h: str | None, limit: int = 3000) -> str | None:
    """HTML description -> plain text with line breaks, capped."""
    if not h:
        return None
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").replace("\u200b", "")
    t = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()
    return t if len(t) <= limit else t[:limit].rstrip() + " ...[cut]"


def _toman(rial: Any) -> int | None:
    """Salaries are Rial per month in the API; the site shows Toman."""
    try:
        return int(rial) // 10 if rial else None
    except (TypeError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _names(items: list[dict] | None) -> list[dict]:
    return [{"slug": x.get("slug"), "name": x.get("title"), "name_fa": x.get("title_farsi")} for x in items or []]


def _job(x: dict) -> dict:
    """One job card from search-by-slug / position/search."""
    b = x.get("brand_data") or {}
    e = x.get("employer") or {}
    loc = x.get("location") or {}
    show = x.get("is_show_salary")
    return {
        "id": x["id"],
        "title": x.get("title"),
        "title_fa": x.get("title_farsi"),
        "company": {
            "id": b.get("uuid"),
            "name": b.get("name_en") or e.get("title"),
            "name_fa": b.get("name_fa") or e.get("name_farsi"),
            "anonymous": bool(x.get("is_anonymous")) or None,
        },
        "city": loc.get("title") or x.get("location_text"),
        "city_fa": loc.get("title_farsi") or x.get("location_text_farsi"),
        "work_type": x.get("work_type"),
        "employment": (x.get("employment_type") or {}).get("title"),
        "seniority": [s.get("title") for s in x.get("seniority") or x.get("seniorities") or []],
        "categories": [c.get("title") for c in x.get("job_category") or x.get("job_categories") or []],
        "salary_toman_per_month": {"from": _toman(x.get("salary_from")), "to": _toman(x.get("salary_to"))}
        if show
        else None,
        "posted": (x.get("lived_at") or "")[:10] or None,
        "urgent": bool(x.get("urgent_at")) or None,
        "url": f"{SITE}/job/{x.get('slug')}/{x['id']}",
    }


def _slugs(v: list[str] | None) -> list[str] | None:
    return [s.strip() for s in v if s.strip()] if v else None


@tool("Search jobs")
async def it_search_jobs(
    keyword: Annotated[
        str | None, Field(description="Job name or ad text words, English or Persian, e.g. python, حسابدار.")
    ] = None,
    locations: Annotated[
        list[str] | None,
        Field(description="City/province slugs from it_lookups('locations'), e.g. ['tehran']."),
    ] = None,
    categories: Annotated[list[str] | None, Field(description="Slugs from it_lookups('categories').")] = None,
    seniority: Annotated[
        list[str] | None,
        Field(description="Slugs from it_lookups('seniority')."),
    ] = None,
    industries: Annotated[list[str] | None, Field(description="Slugs from it_lookups('industries').")] = None,
    employment: Annotated[
        list[str] | None,
        Field(description="Slugs from it_lookups('employment')."),
    ] = None,
    work_type: Annotated[Literal["on_site", "remote", "hybrid"] | None, Field(description="Work arrangement.")] = None,
    company: Annotated[CompanyId | None, Field(description="Only this company's jobs.")] = None,
    urgent: Annotated[bool, Field(description="Only fast-hiring jobs (filters this page only).")] = False,
    military_service: Annotated[bool, Field(description="Only military-service (امریه) ads.")] = False,
    promoted: Annotated[bool, Field(description="Only promoted ads.")] = False,
    page: Page = 1,
) -> dict:
    """Search IranTalent job ads by keyword and filters, newest first.

    Slugs from it_lookups; several in one filter = OR, different filters = AND. Salary is Toman per month, only if
    the employer shows it. Next: it_job, it_company. `total` is the full match count.
    """
    body: dict[str, Any] = {"page": page}
    if keyword and keyword.strip():
        body["keyword"] = keyword.strip()
    for key, val in (
        ("location_slugs", locations),
        ("category_slugs", categories),
        ("seniority_slugs", seniority),
        ("industry_slugs", industries),
        ("employment_slugs", employment),
    ):
        if _slugs(val):
            body[key] = _slugs(val)
    if work_type:
        body["work_type"] = work_type
    if company:
        body["uuid"] = [company]
    if military_service:
        body["is_precept"] = True
    if promoted:
        body["is_boosted"] = True
    d = (await fetch("employer/position/search-by-slug", body=body))["data"]
    jobs = [_job(x) for x in d["data"]]
    if urgent:  # the API ignores is_urgent, so filter the page here
        jobs = [j for j in jobs if j.get("urgent")]
    return {"total": d["total"], "page": d["current_page"], "pages": d["last_page"], "jobs": jobs}


@tool("Job details")
async def it_job(
    job_id: Annotated[int, Field(description="Job id from it_search_jobs.", ge=1)],
) -> dict:
    """Read one IranTalent job ad in full: description, requirements, salary, location, employer, views.

    Use after it_search_jobs. Applying is not possible here.
    """
    x = await fetch(f"employer/position/{job_id}")
    card = _job(x)
    emp = x.get("employer") or {}
    card["company"]["industry"] = (emp.get("industry") or {}).get("title")
    card["company"]["size"] = (emp.get("company_size") or {}).get("title")
    lang = x.get("language")
    # language is fa, en or multi (both texts); Persian first, as the site shows it
    fa, en = x.get("role_description_farsi"), x.get("role_description")
    rfa, ren = x.get("requirements_description_farsi"), x.get("requirements_description")
    card.update(
        reference_code=x.get("reference_code"),
        language=lang,
        description=_text(fa or en),
        description_en=_text(en) if fa and en and lang == "multi" else None,
        requirements=_text(rfa or ren),
        study_fields=[s.get("title") for s in x.get("study_fields") or []],
        min_experience_years=x.get("minimum_experience"),
        gender=x.get("gender"),
        age={"from": x.get("age_from"), "to": x.get("age_to")} if x.get("age_from") or x.get("age_to") else None,
        expires=(x.get("expires_at") or "")[:10] or None,
        views=_int(x.get("view_count")),
        apply_link=x.get("apply_redirect_link") or x.get("redirection_url"),
        status=(x.get("status") or {}).get("title"),
    )
    return card


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _company_row(x: dict) -> dict:
    b = x.get("brand_data") or {}
    return {
        "id": x["uuid"],
        "name": b.get("name_en"),
        "name_fa": b.get("name_fa"),
        "slug": b.get("slug"),
        "rating": _num(x.get("rate")) or None,
        "ratings_count": _int(x.get("review_count")),
        "open_jobs": _int(x.get("position_count")),
        "industry": (b.get("industry") or {}).get("title"),
        "size": (b.get("company_size") or {}).get("title"),
        "city": (b.get("location") or {}).get("title"),
        "url": f"{SITE}/company/{b.get('slug')}/{x['uuid']}/overview",
    }


@tool("Find companies")
async def it_companies(
    search: Annotated[str | None, Field(description="Company name, English or Persian.")] = None,
    page: Page = 1,
) -> dict:
    """List or search IranTalent's employer directory, most open jobs first.

    Use to find a company id from a name. Rating is 1-5 (absent without reviews). Next: it_company,
    it_search_jobs(company=id), it_company_reviews.
    """
    params: dict[str, Any] = {"sort": "-position_count", "page": page}
    if search and search.strip():
        params["search"] = search.strip()
    d = await fetch("candidate/brand", params=params)
    m = d["meta"]
    return {
        "total": m["total"],
        "page": m["current_page"],
        "pages": m["last_page"],
        "companies": [_company_row(x) for x in d["data"]],
    }


@tool("Top rated companies")
async def it_top_companies() -> dict:
    """List IranTalent's 50 top companies by employee rating (1-5).

    Use for "best places to work in Iran". Next: it_company or it_company_reviews.
    """
    d = await fetch("candidate/brand/best-companies")
    rows = [_company_row(x) for x in d["data"]]
    rows.sort(key=lambda r: (-(r["rating"] or 0), -(r["ratings_count"] or 0)))  # the site's order is not by rating
    return {"companies": rows}


@tool("Company profile")
async def it_company(
    company_id: CompanyId,
    jobs: Annotated[int, Field(description="Newest open jobs to include.", ge=0, le=10)] = 5,
) -> dict:
    """Read a company profile: about, industry, size, address, website, rating breakdown and newest open jobs.

    Use after it_companies or it_search_jobs. Ratings are 1-5 averages. Next: it_company_reviews for review text.
    """
    base = f"candidate/brand/{company_id}"
    kinds = ["overall_rate", *RATES]
    brand, tabs, *charts = await asyncio.gather(
        fetch(base),
        fetch(f"{base}/tab-bar"),
        *(fetch(f"{base}/review-score-chart", params={"rate_type": k}) for k in kinds),
    )
    by_kind = dict(zip(kinds, charts, strict=True))
    overall = by_kind.pop("overall_rate")
    out: dict[str, Any] = {
        "id": company_id,
        "name": brand.get("name_en"),
        "name_fa": brand.get("name_fa"),
        "about": _text(brand.get("about_en") or brand.get("about_fa"), 1500),
        "about_fa": _text(brand.get("about_fa"), 1500) if brand.get("about_en") else None,
        "why_work_for_us": _text(brand.get("why_work_for_us_en") or brand.get("why_work_for_us_fa"), 800),
        "benefits": _text(brand.get("benefit_description_en") or brand.get("benefit_description_fa"), 800),
        "industry": (brand.get("industry") or {}).get("title"),
        "size": (brand.get("company_size") or {}).get("title"),
        "city": (brand.get("location") or {}).get("title"),
        "address": brand.get("address_en") or brand.get("address_fa"),
        "founded": brand.get("company_found_year"),
        "website": brand.get("website"),
        "ratings_count": _int(overall.get("total_count")) or None,
        "rating": _num(overall.get("total_average")) if overall.get("total_count") else None,
        "rating_by_category": {k.removesuffix("_rate"): _num(c.get("total_average")) for k, c in by_kind.items()}
        if overall.get("total_count")
        else None,
        "likes": _int((tabs.get("like") or {}).get("like_count")),
        "url": f"{SITE}/company/{brand.get('slug') or ''}/{company_id}/overview" if brand.get("slug") else None,
    }
    if jobs:
        d = (await fetch("employer/position/search-by-slug", body={"uuid": [company_id]}))["data"]
        out["open_jobs"] = d["total"]
        out["jobs"] = [_job(x) for x in d["data"][:jobs]]
    return out


@tool("Company reviews")
async def it_company_reviews(
    company_id: CompanyId,
    sort: Annotated[Literal["newest", "helpful"], Field(description="Order.")] = "newest",
    page: Page = 1,
) -> dict:
    """Read anonymous employee reviews of a company on IranTalent: ratings, pros, cons, reviewer's job title.

    Use for "what is it like to work at X". Ratings are 1-5. Only reviews with written text are listed.
    """
    params = {"sort": "-created_at" if sort == "newest" else "-helpful_count", "page": page}
    d = await fetch(f"candidate/brand/{company_id}/reviews", params=params)
    reviews = []
    for r in d.get("data") or []:
        who = r.get("reviewer") or {}
        reviews.append(
            {
                "date": (r.get("created_at") or "")[:10],
                "overall": _num(r.get("overall_rate")),
                "ratings": {k.removesuffix("_rate"): _int(r.get(k)) for k in RATES},
                "recommends": r.get("recommend") == "1",
                "former_employee": who.get("former_employee") == "1",
                "job_title": who.get("job_title") or who.get("job_title_farsi"),
                "pros": _text(r.get("about"), 1200),
                "cons": _text(r.get("challenge"), 1200),
                "helpful": _int(r.get("helpful_count")),
                "company_replied": bool(r.get("review_reply")) or None,
            }
        )
    return {"total": d.get("total"), "page": d.get("current_page"), "pages": d.get("total_pages"), "reviews": reviews}


@tool("Filter lookups")
async def it_lookups(
    kind: Annotated[
        Literal[
            "categories",
            "industries",
            "seniority",
            "employment",
            "company_size",
            "locations",
            "work_types",
            "salary_specialties",
            "salary_seniority",
        ],
        Field(description="List to return; salary_* feed it_salary_reports / it_salary."),
    ],
) -> dict:
    """List the valid filter values (slug, English and Persian name) for it_search_jobs.

    Call before filtering; slugs must match exactly. Locations include open job counts.
    """
    if kind.startswith("salary_"):
        return {"items": await salary_lookup(kind)}
    if kind == "work_types":
        return {"items": WORK_TYPES}
    if kind == "locations":
        rows = await fetch("public-area/location/provinces-with-position")
        return {
            "items": [
                {
                    "slug": r["slug"],
                    "name": r["title"],
                    "name_fa": r["title_farsi"],
                    "open_jobs": _int(r.get("subscriber")),
                }
                for r in rows
            ]
        }
    rows = await fetch(f"public-area/lookup/{LOOKUPS[kind]}")
    return {"items": _names(rows)}


MARKET = {  # breakdown -> (key in public-area/home-page lookups_with_positions, search filter)
    "categories": "job_categories",
    "industries": "industries",
    "seniority": "seniorities",
    "employment": "employment_types",
}


@tool("Job market overview")
async def it_job_market(
    breakdown: Annotated[
        Literal["categories", "industries", "seniority", "employment", "locations", "companies"],
        Field(description="Grouping."),
    ] = "categories",
) -> dict:
    """Count IranTalent's open jobs by category, industry, seniority, employment type, location or hiring company.

    Use for "which fields hire most" or "who is hiring". Largest first; slugs work in it_search_jobs.
    """
    d = await fetch("public-area/home-page")
    st = d.get("statistics") or {}  # the site dropped this block; the search total is the same number
    total = st.get("live_positions_count")
    if total is None:
        total = (await fetch("employer/position/search-by-slug", body={}))["data"].get("total")
    if breakdown == "companies":
        rows = [
            {
                "id": c["uuid"],
                "name": c.get("company_legal_name_en"),
                "name_fa": c.get("company_legal_name_fa"),
                "open_jobs": _int(c.get("positions_count")),
            }
            for c in d.get("company_with_positions") or []
        ]
    elif breakdown == "locations":
        rows = [
            {"slug": r["slug"], "name": r["title"], "name_fa": r["title_farsi"], "open_jobs": _int(r.get("subscriber"))}
            for r in d.get("provinces_with_positions") or []
        ]
    else:
        rows = [
            {
                "slug": r["slug"],
                "name": r["title"].strip(),
                "name_fa": r["title_farsi"],
                "open_jobs": _int(r.get("position_count")),
            }
            for r in (d.get("lookups_with_positions") or {}).get(MARKET[breakdown]) or []
        ]
    rows.sort(key=lambda r: -(r["open_jobs"] or 0))
    return {
        "open_jobs_total": total,
        "employers_total": st.get("employers_count"),
        "breakdown": breakdown,
        "items": rows,
    }


@tool("Similar jobs")
async def it_similar_jobs(
    job_id: Annotated[int, Field(description="Job id from it_search_jobs.", ge=1)],
    same_city: Annotated[bool, Field(description="Same city only.")] = True,
) -> dict:
    """Find open jobs similar to one ad: same job category (and city), newest first.

    Use after it_job for "more like this".
    """
    x = await fetch(f"employer/position/{job_id}")
    cats = [c["slug"] for c in x.get("job_category") or x.get("job_categories") or [] if c.get("slug")]
    if not cats:
        raise ApiError("This ad has no job category to match on; use it_search_jobs with a keyword.")
    body: dict[str, Any] = {"category_slugs": cats[:1]}
    if same_city and (x.get("location") or {}).get("slug"):
        body["location_slugs"] = [x["location"]["slug"]]
    d = (await fetch("employer/position/search-by-slug", body=body))["data"]
    return {"total": d["total"], "jobs": [_job(j) for j in d["data"] if j["id"] != job_id][:15]}
