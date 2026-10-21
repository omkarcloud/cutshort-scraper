# 💼 Cutshort Scraper

Cutshort Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Cutshort job data for free.

## ✨ What Can I Get?

- 💼 **44,000+ live tech jobs across India** — full description, INR salary band, experience, skills, remote policy & recruiter
- 🔍 **Search 3,700+ skills and roles in 14 cities** — filter by remote, experience, salary, company type & posting date
- 🏢 **16,000+ company pages** — size, stage, funding, socials, hiring team, open jobs & similar companies
- 💰 **Salaries for 37 tech roles in 16 locations** — top 5/10/20% pay, trends by city and role, plus 98 ready-made job descriptions

## 🎥 Example: A Full Cutshort Job

```json
{
  "id": "M0Q0hQLR",
  "title": "Senior Software Engineer - AI Garage - HYD",
  "link": "https://cutshort.io/job/Senior-Software-Engineer-AI-Garage-HYD-Hyderabad-Google-M0Q0hQLR",
  "company": {
    "name": "Google",
    "alias": "google-xCGJDIoH",
    "type": "Product",
    "stage": "Profitable",
    "founded_year": 1998,
    "followers_count": 1671,
    "website": "https://google.com"
  },
  "locations": ["Hyderabad"],
  "remote_policy": "onsite",
  "role_types": ["full_time"],
  "experience": { "min_years": 6.0, "max_years": 15.0, "text": "6 - 15 years" },
  "salary": { "currency": "INR", "min_lakhs": null, "max_lakhs": null, "has_esop": false, "text": "Best in industry" },
  "skills": [
    { "code": "06852", "name": "Agentic AI" },
    { "code": "06781", "name": "Retrieval Augmented Generation (RAG)" }
  ],
  "description": "Responsibilities\n- Engineering technical lead for the AI Garage team which responsible for developing AI/ML systems and Agentic solutions in HR domain\n- Drive engineering excellence for the AI Garage team ...",
  "recruiter": { "name": "Veena Suresh" },
  "posted_on": "2026-09-28",
  "is_live": true
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Cutshort Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/cutshort-scraper
cd cutshort-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/jobs/details?job=M0Q0hQLR"
```

```json
{
  "id": "M0Q0hQLR",
  "record_id": "6ab0f9a5a8afac69f1586404",
  "title": "Senior Software Engineer - AI Garage - HYD",
  "link": "https://cutshort.io/job/Senior-Software-Engineer-AI-Garage-HYD-Hyderabad-Google-M0Q0hQLR",
  "company": {
    "name": "Google",
    "link": "https://cutshort.io/company/google-xCGJDIoH",
    "linkedin": "https://linkedin.com/company/google"
  },
  "locations": ["Hyderabad"],
  "is_remote": false,
  "experience": { "min_years": 6.0, "max_years": 15.0, "text": "6 - 15 years" },
  "skills": [
    { "code": "06852", "name": "Agentic AI" },
    { "code": "00268", "name": "Machine Learning (ML)" }
  ],
  "posted_at": "2026-09-28T10:37:25Z",
  "category": "tech"
}
```

All 16 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

16 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Job Details | `/jobs/details` | The full job: description, salary, skills, recruiter and company |
| Search Jobs | `/jobs/search` | 50 full jobs per page by skill, city, remote, salary, experience |
| Batch Job Details | `/jobs/batch` | Full details for up to 10 jobs in one call |
| Similar Jobs | `/jobs/similar` | The 10 jobs Cutshort recommends next to any job |
| Company Details | `/companies/details` | Size, stage, funding, socials, hiring team and open jobs |
| Company Jobs | `/companies/jobs` | Every open job a company has posted, newest first |
| Search Companies | `/companies/search` | Companies by name with logo, website, size and funding |
| Company Directory | `/companies/directory` | 50 companies per page by industry and city |
| Salaries | `/salaries` | Top 5/10/20% pay for a role, plus city and role trends |
| Job Description | `/job-descriptions/details` | A ready-to-use job description with responsibilities and requirements |
| Autocomplete | `/autocomplete` | Skill, company, job title and location suggestions |
| Job Categories | `/jobs/categories` | 20,000+ job listings by skill, city and remote |
| Company Directories | `/companies/categories` | All 563 company directories by industry and city |
| Salary Roles | `/salaries/titles` | The 37 roles with salary data and their locations |
| Job Description Roles | `/job-descriptions` | The 98 roles with a ready-made job description |
| Locations | `/locations` | The 14 job cities and 16 salary locations |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-cutshort-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-cutshort-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-cutshort-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/jobs/search",
    params={"query": "python", "location": "bangalore"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Cutshort Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Cutshort%20Scraper%20API.)

[![Ask Us by Email about Cutshort Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Cutshort%20Scraper%20API&body=I%20need%20help%20using%20the%20Cutshort%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**Jobstreet Scraper**](https://github.com/omkarcloud/jobstreet-scraper) — JobStreet & JobsDB jobs, salaries, companies & reviews across 6 Asian markets
- [**Hirist Scraper**](https://github.com/omkarcloud/hirist-scraper) — Hirist IT jobs, company ratings, recruiters & skills with live job counts
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/cutshort-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/cutshort-scraper)
