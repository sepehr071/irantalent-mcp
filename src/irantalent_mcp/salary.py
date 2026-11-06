"""IranTalent salary reports (salary.irantalent.com, a WordPress site): national net monthly salary percentiles."""

from __future__ import annotations

import asyncio
import html
import re
from typing import Annotated, Any

from pydantic import Field

from .http import SALARY, ApiError, fetch
from .registry import tool

WP = "wp-json/wp/v2"
PER_PAGE = 30
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٫٬", "0123456789.,")
BAR = re.compile(r'data-percentile="(\d+)" data-year="(\d+)".*?srp-hbar__value">([^<]*)<', re.S)
SalarySlug = Annotated[
    str, Field(description="Salary report slug from it_salary_reports, e.g. java-senior-salary.", pattern=r"^[\w-]+$")
]


async def _taxonomy(name: str) -> list[dict]:
    return await fetch(f"{WP}/{name}", {"per_page": 100, "_fields": "id,slug,name"}, salary=True)


async def _reports() -> list[dict]:
    """All reports (about 200) with their specialty and seniority names; two cached calls."""
    spec, sen = await asyncio.gather(_taxonomy("salary-specialty"), _taxonomy("salary-seniority"))
    pages: list[list[dict]] = []
    for p in range(1, 6):
        try:
            rows = await fetch(
                f"{WP}/salary-report",
                {"per_page": 100, "page": p, "_fields": "slug,title,salary-specialty,salary-seniority"},
                salary=True,
            )
        except ApiError as e:
            if e.status == 400 and p > 1:  # WordPress answers 400 for a page past the end
                break
            raise
        pages.append(rows)
        if len(rows) < 100:
            break
    specs, sens = {x["id"]: x for x in spec}, {x["id"]: x for x in sen}
    out = []
    for r in (r for page in pages for r in page):
        sp = specs.get((r.get("salary-specialty") or [0])[0]) or {}
        se = sens.get((r.get("salary-seniority") or [0])[0]) or {}
        out.append(
            {
                "slug": r["slug"],
                "title": html.unescape(r["title"]["rendered"]),
                "specialty": sp.get("name"),
                "specialty_slug": sp.get("slug"),
                "seniority": se.get("name"),
                "seniority_slug": se.get("slug"),
                "url": f"{SALARY}/salary-report/{r['slug']}/",
            }
        )
    return out


def _million(s: str) -> float | None:
    m = re.search(r"[\d.]+", s.translate(DIGITS))
    return float(m.group()) if m else None


def _parse(page: str) -> dict[str, dict[str, int]]:
    """Percentile bars of the report page: {year: {p10..p90: Toman per month}}. Values are shown in million Toman."""
    years: dict[str, dict[str, int]] = {}
    for pct, year, val in BAR.findall(page):
        if (v := _million(val)) is not None:
            years.setdefault(year, {})[f"p{pct}"] = round(v * 1_000_000)
    return years


async def _report(meta: dict) -> dict:
    years = _parse(await fetch(f"salary-report/{meta['slug']}/", salary=True, text=True))
    if not years:
        raise ApiError(f"No salary figures found on {meta['url']} (the page layout may have changed).")
    return {
        "title": meta["title"],
        "specialty": meta["specialty"],
        "seniority": meta["seniority"],
        "monthly_net_toman_by_persian_year": {y: years[y] for y in sorted(years, reverse=True)},
        "url": meta["url"],
    }


@tool("Salary reports")
async def it_salary_reports(
    search: Annotated[
        str | None,
        Field(description="Report slug part, Persian name or specialty, e.g. java, حسابداری."),
    ] = None,
    seniority: Annotated[
        str | None,
        Field(description="Slug from it_lookups('salary_seniority'), e.g. junior, senior."),
    ] = None,
    page: Annotated[int, Field(description="1-based; 30 per page.", ge=1, le=20)] = 1,
) -> dict:
    """List IranTalent salary reports: one per job specialty and seniority level (about 200).

    Use first for "how much does a X earn in Iran". Next: it_salary with the slug.
    """
    rows = await _reports()
    q = (search or "").strip().lower()
    if q:
        rows = [r for r in rows if q in f"{r['slug']} {r['title']} {r['specialty']}".lower()]
    if seniority:
        rows = [r for r in rows if r["seniority_slug"] == seniority.strip()]
    start = (page - 1) * PER_PAGE
    keep = ("slug", "title", "specialty", "specialty_slug", "seniority", "seniority_slug")
    return {
        "total": len(rows),
        "page": page,
        "pages": -(-len(rows) // PER_PAGE),
        "reports": [{k: r[k] for k in keep} for r in rows[start : start + PER_PAGE]],
    }


@tool("Salary figures")
async def it_salary(
    report: Annotated[str | None, Field(description="One report slug from it_salary_reports.")] = None,
    specialty: Annotated[
        str | None,
        Field(description="Slug from it_lookups('salary_specialties'), e.g. java: all seniority levels."),
    ] = None,
) -> dict:
    """Read the salary figures of one IranTalent salary report, or of every seniority level of one specialty.

    Give exactly one of report or specialty. Figures: national net monthly Toman at p10/p25/p50/p75/p90, Persian
    year 1405 (requested) and 1404 (received), from the survey, not ads. No city split.
    """
    if bool(report) == bool(specialty):
        raise ApiError("Give exactly one of report or specialty.")
    rows = await _reports()
    if report:
        meta = next((r for r in rows if r["slug"] == report.strip()), None)
        if not meta:
            raise ApiError(f"No salary report '{report}'. Find the slug with it_salary_reports.")
        return await _report(meta)
    metas = [r for r in rows if r["specialty_slug"] == specialty.strip()]
    if not metas:
        raise ApiError(f"No salary specialty '{specialty}'. Use it_lookups(kind='salary_specialties').")
    levels = await asyncio.gather(*(_report(m) for m in metas[:8]))
    return {"specialty": metas[0]["specialty"], "levels": levels}


async def salary_lookup(kind: str) -> list[dict[str, Any]]:
    """Specialty or seniority slugs of the salary reports, for it_lookups."""
    rows = await _reports()
    key = "specialty" if kind == "salary_specialties" else "seniority"
    seen: dict[str, dict] = {}
    for r in rows:
        if r[f"{key}_slug"]:
            e = seen.setdefault(r[f"{key}_slug"], {"slug": r[f"{key}_slug"], "name_fa": r[key], "reports": 0})
            e["reports"] += 1
    return sorted(seen.values(), key=lambda e: (-e["reports"], e["slug"]))
