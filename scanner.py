import json
import re
import requests
from datetime import datetime, timezone

BASE_URL = "https://api.dealwork.ai"

SEARCHES = [
    "reels",
    "shorts",
    "short form video",
    "instagram video",
    "tiktok video",
    "ugc video",
    "video editor",
]

MIN_PRICE = 30

VIDEO_WORDS = [
    "reel", "reels", "short", "shorts",
    "short-form", "short form",
    "tiktok", "instagram", "youtube",
    "ugc", "video", "videos"
]

REPEAT_WORDS = [
    "ongoing", "recurring", "long-term",
    "long term", "weekly", "monthly",
    "daily", "per week", "per month"
]

BRIEF_WORDS = [
    "script", "brief", "reference",
    "raw footage", "assets", "voiceover",
    "requirements", "examples"
]

BAD_WORDS = [
    "unpaid", "free work", "free sample",
    "exposure only"
]


def text(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        return " ".join(text(x) for x in value)

    if isinstance(value, dict):
        return " ".join(text(v) for v in value.values())

    return ""


def search_jobs(query):
    """
    Try Dealwork's search endpoint.

    We keep this read-only:
    no bidding, no contracts, no payments.
    """

    endpoints = [
        f"{BASE_URL}/api/v1/jobs/search",
        f"{BASE_URL}/api/v1/search/jobs",
    ]

    for endpoint in endpoints:

        try:
            response = requests.get(
                endpoint,
                params={
                    "q": query,
                    "limit": 100
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "video-job-scanner/2.0"
                },
                timeout=30
            )

            if response.status_code != 404:
                response.raise_for_status()

                data = response.json()

                if isinstance(data, list):
                    return data

                if isinstance(data, dict):
                    for key in [
                        "jobs",
                        "data",
                        "items",
                        "results"
                    ]:
                        if isinstance(data.get(key), list):
                            return data[key]

        except Exception as error:
            print(
                f"Search failed for '{query}': {error}"
            )

    return []


def money_values(value):
    s = text(value)

    values = []

    for match in re.findall(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        s
    ):
        values.append(
            float(match.replace(",", ""))
        )

    for match in re.findall(
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|USDC)",
        s,
        re.I
    ):
        values.append(
            float(match.replace(",", ""))
        )

    return values


def analyse(job):

    full_text = text(job).lower()

    video_hits = [
        x for x in VIDEO_WORDS
        if x in full_text
    ]

    repeat_hits = [
        x for x in REPEAT_WORDS
        if x in full_text
    ]

    brief_hits = [
        x for x in BRIEF_WORDS
        if x in full_text
    ]

    bad_hits = [
        x for x in BAD_WORDS
        if x in full_text
    ]

    prices = money_values(job)

    budget = max(prices) if prices else 0

    score = 0

    if video_hits:
        score += 5

    if repeat_hits:
        score += 4

    if len(repeat_hits) >= 2:
        score += 2

    if len(brief_hits) >= 2:
        score += 3

    if budget >= MIN_PRICE:
        score += 4

    if bad_hits:
        score -= 10

    if not video_hits:
        return None

    return {
        "score": score,
        "budget_found": budget,
        "video_keywords": video_hits,
        "repeat_keywords": repeat_hits,
        "brief_keywords": brief_hits,
        "warnings": bad_hits,
        "job": job
    }


def main():

    print("VIDEO JOB SCANNER V2")
    print("=" * 50)

    all_jobs = {}

    for query in SEARCHES:

        print(f"Searching: {query}")

        jobs = search_jobs(query)

        print(
            f"  Results: {len(jobs)}"
        )

        for job in jobs:

            job_id = (
                job.get("id")
                or job.get("jobId")
                or str(job)
            )

            all_jobs[str(job_id)] = job

    jobs = list(all_jobs.values())

    print()
    print(
        f"Unique jobs found: {len(jobs)}"
    )

    analysed = []

    for job in jobs:

        result = analyse(job)

        if result:
            analysed.append(result)

    analysed.sort(
        key=lambda x: (
            x["score"],
            x["budget_found"]
        ),
        reverse=True
    )

    qualified = [
        x for x in analysed
        if x["score"] >= 8
    ]

    print(
        f"Video jobs: {len(analysed)}"
    )

    print(
        f"Potential matches: {len(qualified)}"
    )

    print()

    for i, result in enumerate(
        qualified[:20],
        1
    ):

        job = result["job"]

        title = (
            job.get("title")
            or job.get("name")
            or "Untitled"
        )

        job_id = (
            job.get("id")
            or job.get("jobId")
            or "unknown"
        )

        url = (
            job.get("url")
            or job.get("link")
            or ""
        )

        print("=" * 50)

        print(f"#{i}")
        print(f"Title: {title}")
        print(f"ID: {job_id}")
        print(
            f"Budget found: "
            f"${result['budget_found']}"
        )

        print(
            f"Score: {result['score']}"
        )

        print(
            f"URL: {url}"
        )

        print(
            "Recurring:",
            ", ".join(
                result["repeat_keywords"]
            )
        )

    output = {
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "searches": SEARCHES,

        "jobs_found": len(jobs),

        "video_jobs": len(analysed),

        "potential_matches": len(qualified),

        "matches": qualified[:20]
    }

    with open(
        "matches.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("Saved matches.json")


if __name__ == "__main__":
    main()
