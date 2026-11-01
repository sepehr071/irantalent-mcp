import json

import httpx
import pytest
from conftest import fixture, page

pytestmark = pytest.mark.anyio

UUID = "faa00b2d-29c2-46ad-9d9a-15cff9324abf"
P = "/api/v1/"
TOOLS = {
    "it_search_jobs",
    "it_job",
    "it_companies",
    "it_top_companies",
    "it_company",
    "it_company_reviews",
    "it_lookups",
    "it_job_market",
    "it_similar_jobs",
    "it_salary_reports",
    "it_salary",
}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert "title" not in str(t.input_schema.get("properties", {}).values()), t.name


async def test_calls_send_the_headers_chrome_sends_per_host_and_page_type(api):
    from irantalent_mcp import http

    for path in ("/api/v1/x", "/wp-json/wp/v2/y", "/salary-report/z/"):
        api[path] = {}
    await http.fetch("x")  # the web app's fetch(): cross-subdomain, JSON content type even on GET
    await http.fetch("wp-json/wp/v2/y", salary=True)
    await http.fetch("salary-report/z/", salary=True, text=True)
    app, wp, page = (c.headers for c in api.calls)
    assert (app["accept"], app["content-type"], app["origin"], app["referer"], app["sec-fetch-site"]) == (
        "application/json",
        "application/json",
        "https://www.irantalent.com",
        "https://www.irantalent.com/",
        "same-site",
    )
    assert (app["sec-fetch-mode"], app["sec-fetch-dest"], app["priority"], app["accept-language"]) == (
        "cors",
        "empty",
        "u=1, i",
        "fa",
    )
    assert wp["sec-fetch-site"] == "same-origin" and "origin" not in wp and "content-type" not in wp
    assert (page["sec-fetch-mode"], page["sec-fetch-dest"], page["priority"]) == ("navigate", "document", "u=0, i")
    assert (
        page["accept"].startswith("text/html,application/xhtml+xml")
        and page["referer"] == "https://salary.irantalent.com/"
    )


async def test_search_builds_slug_body_and_trims_cards(client, api):
    api[P + "employer/position/search-by-slug"] = fixture("search.json")
    r = (
        await client.call_tool(
            "it_search_jobs",
            {"keyword": " python ", "locations": ["tehran"], "work_type": "remote", "company": UUID, "page": 2},
        )
    ).structured_content
    body = json.loads(api.calls[0].content)
    assert body == {
        "page": 2,
        "keyword": "python",
        "location_slugs": ["tehran"],
        "work_type": "remote",
        "uuid": [UUID],
    }
    assert api.calls[0].method == "POST"
    job = r["jobs"][0]
    assert r["total"] >= 3 and len(r["jobs"]) == 3
    assert job["url"].startswith("https://www.irantalent.com/job/") and job["company"]["id"]
    assert "role_description" not in job


async def test_search_converts_salary_rial_to_toman(client, api):
    d = fixture("search.json")
    d["data"]["data"][0].update(is_show_salary=True, salary_from=450000000, salary_to=600000000)
    d["data"]["data"][1]["is_show_salary"] = False
    api[P + "employer/position/search-by-slug"] = d
    jobs = (await client.call_tool("it_search_jobs", {})).structured_content["jobs"]
    assert jobs[0]["salary_toman_per_month"] == {"from": 45_000_000, "to": 60_000_000}
    assert "salary_toman_per_month" not in jobs[1]


async def test_invalid_slug_error_is_explained(client, api):
    api[P + "employer/position/search-by-slug"] = lambda r: httpx.Response(
        422, json={"message": "x", "errors": {"industry_slugs.0": ["The selected industry_slugs.0 is invalid."]}}
    )
    res = await client.call_tool("it_search_jobs", {"industries": ["nope"]})
    assert res.is_error and "it_lookups" in res.content[0].text and "invalid" in res.content[0].text


async def test_job_detail_has_text_not_html(client, api):
    api[P + "employer/position/185914"] = fixture("position.json")
    r = (await client.call_tool("it_job", {"job_id": 185914})).structured_content
    assert r["id"] == 185914 and r["company"]["id"] and r["views"] > 0
    assert "<p" not in r["description"] and "&nbsp;" not in r["description"]


async def test_companies_search_uses_search_param(client, api):
    api[P + "candidate/brand"] = fixture("brands.json")
    r = (await client.call_tool("it_companies", {"search": "taxi"})).structured_content
    q = api.calls[0].url.params
    assert q["search"] == "taxi" and q["sort"] == "-position_count"
    assert r["total"] > 1000 and r["companies"][0]["id"] == UUID and r["companies"][0]["rating"] > 3


async def test_company_profile_with_rating_and_jobs(client, api):
    api[P + f"candidate/brand/{UUID}"] = fixture("brand.json")
    api[P + f"candidate/brand/{UUID}/tab-bar"] = fixture("tab_bar.json")
    api[P + f"candidate/brand/{UUID}/review-score-chart"] = fixture("chart.json")
    api[P + "employer/position/search-by-slug"] = fixture("company_jobs.json")
    r = (await client.call_tool("it_company", {"company_id": UUID, "jobs": 2})).structured_content
    assert r["name"] == "Taxi Maxim" and r["ratings_count"] > 0 and 1 <= r["rating"] <= 5
    assert 1 <= r["rating_by_category"]["culture_and_value"] <= 5
    assert r["open_jobs"] == 74 and len(r["jobs"]) == 2 and json.loads(api.calls[-1].content) == {"uuid": [UUID]}


async def test_company_reviews_are_trimmed(client, api):
    api[P + f"candidate/brand/{UUID}/reviews"] = fixture("reviews.json")
    r = (await client.call_tool("it_company_reviews", {"company_id": UUID, "sort": "helpful"})).structured_content
    assert api.calls[0].url.params["sort"] == "-helpful_count"
    first = r["reviews"][0]
    assert r["total"] == 2 and first["pros"] and first["job_title"] == "Chief Financial Officer"
    assert first["recommends"] is True and "brand" not in first


async def test_top_companies(client, api):
    api[P + "candidate/brand/best-companies"] = fixture("best.json")
    r = (await client.call_tool("it_top_companies", {})).structured_content
    assert len(r["companies"]) == 3 and r["companies"][0]["id"]


async def test_lookups(client, api):
    api[P + "public-area/lookup/42"] = fixture("lookup42.json")
    api[P + "public-area/location/provinces-with-position"] = fixture("prov.json")
    cats = (await client.call_tool("it_lookups", {"kind": "categories"})).structured_content["items"]
    assert any(c["slug"] == "hse-health-safety-environment" for c in cats)
    locs = (await client.call_tool("it_lookups", {"kind": "locations"})).structured_content["items"]
    assert any(c["slug"] == "tehran" and c["open_jobs"] > 100 for c in locs)
    wt = (await client.call_tool("it_lookups", {"kind": "work_types"})).structured_content["items"]
    assert {w["slug"] for w in wt} == {"on_site", "remote", "hybrid"}


async def test_bad_company_id_rejected(client):
    res = await client.call_tool("it_company", {"company_id": "not-a-uuid"})
    assert res.is_error


def salary_routes(api):
    api["/wp-json/wp/v2/salary-specialty"] = fixture("wp_specialty.json")
    api["/wp-json/wp/v2/salary-seniority"] = fixture("wp_seniority.json")
    api["/wp-json/wp/v2/salary-report"] = lambda r: (
        httpx.Response(200, json=fixture("wp_reports.json"))
        if r.url.params["page"] == "1"
        else httpx.Response(200, json=[])
    )
    api["/salary-report/java-senior-salary/"] = page("salary_report.html")
    api["/salary-report/java-junior-salary/"] = page("salary_report.html")


async def test_salary_reports_search_and_filter(client, api):
    salary_routes(api)
    r = (await client.call_tool("it_salary_reports", {"search": "JAVA"})).structured_content
    assert r["total"] == 2 and {x["seniority_slug"] for x in r["reports"]} == {"junior", "senior"}
    r = (await client.call_tool("it_salary_reports", {"seniority": "senior"})).structured_content
    assert [x["slug"] for x in r["reports"]] == ["java-senior-salary"]


async def test_salary_parses_percentile_bars(client, api):
    salary_routes(api)
    r = (await client.call_tool("it_salary", {"report": "java-senior-salary"})).structured_content
    y = r["monthly_net_toman_by_persian_year"]
    assert y["1405"] == {
        "p90": 155_000_000,
        "p75": 133_000_000,
        "p50": 117_000_000,
        "p25": 90_000_000,
        "p10": 84_000_000,
    }
    assert y["1404"]["p50"] == 73_000_000
    r = (await client.call_tool("it_salary", {"specialty": "java"})).structured_content
    assert len(r["levels"]) == 2


async def test_salary_needs_exactly_one_selector(client, api):
    salary_routes(api)
    assert (await client.call_tool("it_salary", {})).is_error
    assert (await client.call_tool("it_salary", {"report": "nope"})).is_error


async def test_salary_lookups(client, api):
    salary_routes(api)
    items = (await client.call_tool("it_lookups", {"kind": "salary_specialties"})).structured_content["items"]
    assert items[0]["slug"] == "java" and items[0]["reports"] == 2


async def test_job_market_sorted_counts(client, api):
    api[P + "public-area/home-page"] = fixture("home.json")
    r = (await client.call_tool("it_job_market", {"breakdown": "industries"})).structured_content
    counts = [x["open_jobs"] for x in r["items"]]
    assert counts == sorted(counts, reverse=True) and r["open_jobs_total"] > 0
    r = (await client.call_tool("it_job_market", {"breakdown": "companies"})).structured_content
    assert r["items"][0]["id"]


async def test_job_market_without_statistics_block(client, api):
    api[P + "public-area/home-page"] = fixture("home_nostats.json")
    api[P + "employer/position/search-by-slug"] = fixture("search.json")
    r = (await client.call_tool("it_job_market", {"breakdown": "seniority"})).structured_content
    assert r["open_jobs_total"] > 0 and r["items"] and r["employers_total"] is None


async def test_new_search_flags_and_urgent_page_filter(client, api):
    api[P + "employer/position/search-by-slug"] = fixture("search.json")
    r = (
        await client.call_tool("it_search_jobs", {"military_service": True, "promoted": True, "urgent": True})
    ).structured_content
    body = json.loads(api.calls[0].content)
    assert body["is_precept"] is True and body["is_boosted"] is True and "is_urgent" not in body
    assert r["jobs"] == [] or all(j["urgent"] for j in r["jobs"])


async def test_similar_jobs_excludes_self(client, api):
    api[P + "employer/position/182594"] = fixture("position.json")
    api[P + "employer/position/search-by-slug"] = fixture("search.json")
    r = (await client.call_tool("it_similar_jobs", {"job_id": 182594})).structured_content
    body = json.loads(api.calls[1].content)
    assert body["category_slugs"] and body["location_slugs"]
    assert all(j["id"] != 182594 for j in r["jobs"])
