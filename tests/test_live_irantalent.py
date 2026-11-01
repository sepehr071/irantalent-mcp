import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]

TAXI = "faa00b2d-29c2-46ad-9d9a-15cff9324abf"  # Taxi Maxim


async def test_live_search_keyword(client):
    r = (await client.call_tool("it_search_jobs", {"keyword": "python"})).structured_content
    assert r["total"] > 0 and r["jobs"] and r["jobs"][0]["url"].startswith("https://www.irantalent.com/job/")


async def test_live_search_filters_and_detail(client):
    r = (
        await client.call_tool(
            "it_search_jobs", {"locations": ["tehran"], "seniority": ["top-management-director"], "page": 1}
        )
    ).structured_content
    assert r["total"] > 0 and all(j["city"] == "Tehran" for j in r["jobs"] if j.get("city"))
    d = (await client.call_tool("it_job", {"job_id": r["jobs"][0]["id"]})).structured_content
    assert d["id"] == r["jobs"][0]["id"] and d["title"] == r["jobs"][0]["title"]


async def test_live_company_flow(client):
    c = (await client.call_tool("it_companies", {"search": "nestle"})).structured_content
    assert any("Nestle" in (x["name"] or "") for x in c["companies"])
    p = (await client.call_tool("it_company", {"company_id": TAXI, "jobs": 2})).structured_content
    assert p["name"] == "Taxi Maxim" and p["ratings_count"] > 0 and 1 <= p["rating"] <= 5
    rv = (await client.call_tool("it_company_reviews", {"company_id": TAXI})).structured_content
    assert rv["reviews"] and "overall" in rv["reviews"][0]


async def test_live_top_and_lookups(client):
    t = (await client.call_tool("it_top_companies", {})).structured_content
    assert len(t["companies"]) > 10
    for kind in ("categories", "industries", "seniority", "employment", "company_size", "locations", "work_types"):
        items = (await client.call_tool("it_lookups", {"kind": kind})).structured_content["items"]
        assert items, kind


async def test_live_salary(client):
    r = (await client.call_tool("it_salary_reports", {"search": "java"})).structured_content
    assert r["total"] > 0
    s = (await client.call_tool("it_salary", {"report": "java-senior-salary"})).structured_content
    y = s["monthly_net_toman_by_persian_year"]
    assert y and all(v["p10"] < v["p50"] < v["p90"] for v in y.values())
    assert (await client.call_tool("it_salary", {"specialty": "java"})).structured_content["levels"]


async def test_live_market_and_similar(client):
    m = (await client.call_tool("it_job_market", {"breakdown": "categories"})).structured_content
    assert m["open_jobs_total"] > 100 and m["items"][0]["open_jobs"] >= m["items"][-1]["open_jobs"]
    j = (await client.call_tool("it_search_jobs", {"military_service": True})).structured_content
    assert j["total"] >= 0
    first = (await client.call_tool("it_search_jobs", {})).structured_content["jobs"][0]["id"]
    s = (await client.call_tool("it_similar_jobs", {"job_id": first})).structured_content
    assert all(x["id"] != first for x in s["jobs"])
