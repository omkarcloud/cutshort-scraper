"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json.
"""
import json
import os

from cutshort import companies, jobs

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a job ID, slug or any cutshort.io job link
    save("job_M0Q0hQLR.json", jobs.details("M0Q0hQLR"))

    # 50 jobs per page, newest first, full details on each
    save("search_python_bangalore.json", jobs.search(query={"text": "python", "slug": None},
                                                     location="bangalore-bengaluru"))

    # a company page by name, link or alias
    save("company_google.json", companies.details({"alias": None, "name": "Google"}))
