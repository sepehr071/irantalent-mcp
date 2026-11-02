<!-- mcp-name: io.github.sepehr071/irantalent-mcp -->

<div align="center">

# irantalent-mcp: IranTalent (ایران‌تلنت) jobs and company reviews MCP server for AI agents

**irantalent-mcp is an unofficial, read-only MCP server that gives AI agents IranTalent (irantalent.com), the professional job portal for Iran.**<br>
Its 7 tools search about 2,000 live job ads with filters, read an ad in full, find companies among 34,000 employers,<br>
and read company profiles, rating breakdowns and anonymous employee reviews.<br>
No API key or IranTalent account is needed. It works in Claude, Cursor, Copilot and any other MCP client.

[![PyPI](https://img.shields.io/pypi/v/irantalent-mcp?color=2563eb)](https://pypi.org/project/irantalent-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/irantalent-mcp)](https://pypi.org/project/irantalent-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/irantalent-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [What it can do](#what-it-can-do) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for irantalent.com: job search with filters, job ad details, company directory, company profiles, rating breakdowns and employee reviews.
- **Install:** `uvx irantalent-mcp` or `claude mcp add irantalent -- uvx irantalent-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `IRANTALENT_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, apply, post jobs or write reviews, so no confirmation is needed before calling any tool.
- **Tools:** 11, all prefixed `it_`. Typical sequences: `it_lookups` -> `it_search_jobs` -> `it_job`; `it_companies` -> `it_company` -> `it_company_reviews`.
- **Use when:** the user wants jobs in Iran by keyword, city, field, seniority, industry or remote work, the full text of an ad, the salary an employer published, or what employees say about a company.
- **Do not use when:** the user wants to apply, upload a CV or see candidate data (those need an account).
- **Output:** compact JSON. Salaries are Toman per month, shown only when the employer publishes them. Ads and company texts are mostly Persian.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/irantalent-mcp/blob/main/server.json) and the
  [iran-mcp catalog](https://github.com/sepehr071/iran-mcp).

## Quick start

```bash
claude mcp add irantalent -- uvx irantalent-mcp
```

Other clients: run `uvx irantalent-mcp` as a stdio server.

## What it can do

- **Search jobs** by keyword plus city, job category, seniority, industry, employment type, on-site/remote/hybrid, one company or fast hiring
- **Read an ad**: description, requirements, study fields, experience, published salary, views, employer
- **Find companies** by name in a directory of about 34,000 employers, with rating, review count and open jobs
- **Top companies**: the site's 50 best rated employers
- **Company profile**: about text, industry, size, address, website, rating by category, newest jobs
- **Employee reviews**: anonymous pros and cons with six ratings each
- **Filter lookups**: valid slugs for every filter, locations with job counts

Example prompts:

- "Remote Python jobs on IranTalent."
- "Senior management jobs in Tehran in the pharmaceutical industry."
- "Is Digikala a good employer? What do employees say?"
- <span dir="rtl">آگهی‌های استخدام حسابدار در اصفهان را پیدا کن.</span>

## Tools

| Tool | What it does |
|---|---|
| `it_search_jobs` | Jobs by keyword and filters (slugs), 30 per page, newest first |
| `it_job` | One ad in full |
| `it_companies` | Search the company directory by name |
| `it_top_companies` | 50 best rated companies, sorted by rating (then rating count) |
| `it_company` | Profile, rating breakdown, newest jobs |
| `it_company_reviews` | Employee reviews, 30 per page |
| `it_lookups` | Filter slugs: categories, industries, seniority, employment, company size, locations, work types, salary specialties and seniority |
| `it_job_market` | Open job counts by category, industry, seniority, employment, city or hiring company |
| `it_similar_jobs` | Open jobs like one ad (same category and city) |
| `it_salary_reports` | List the salary survey reports (about 200 specialty and seniority pages) |
| `it_salary` | National net monthly salary percentiles (p10 to p90, years 1404 and 1405) for a report or a whole specialty |

## FAQ

**Does it need an account?** No. It reads the same public data the site shows to anyone.

**Why can't I filter by date or sort?** The public search API ignores those parameters; results are newest first.

**Where does it work?** Both the direct Iranian line and a foreign proxy worked when tested. Set `IRANTALENT_MCP_PROXY` if your network blocks it.

**Is it official?** No. It is an unofficial tool and not affiliated with IranTalent.

## فارسی

<div dir="rtl">

`irantalent-mcp` یک سرور MCP غیررسمی و فقط‌خواندنی برای ایران‌تلنت است. با آن می‌توان آگهی‌های استخدام را با فیلتر شهر، گروه شغلی، رده سازمانی، صنعت و دورکاری جست‌وجو کرد، متن کامل آگهی را خواند و دربارهٔ شرکت‌ها امتیاز و نظر کارکنان را دید. نیازی به حساب کاربری یا کلید API نیست.

نصب: `claude mcp add irantalent -- uvx irantalent-mcp`

</div>

---

Made by [Sepehr Radmard](https://github.com/sepehr071) ([LinkedIn](https://linkedin.com/in/sepehr-radmard)). MIT license.
