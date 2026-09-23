import json
import re
import requests
from datetime import datetime, timezone

API_URL = "https://api.dealwork.ai/api/v1/jobs"

MIN_PRICE = 30

VIDEO_WORDS = [
    "reel", "reels",
    "short", "shorts",
    "short-form",
    "tiktok",
    "instagram",
    "youtube",
    "ugc",
    "video",
    "videos",
    "vertical video",
    "social media video",
]

RECURRING_WORDS = [
    "ongoing",
    "recurring",
    "long term",
    "long-term",
    "weekly",
    "monthly",
    "daily",
    "multiple videos",
    "multiple reels",
    "per week",
    "per month",
    "every week",
]

GOOD_BRIEF_WORDS = [
    "script",
    "brief",
    "reference",
    "raw footage",
    "assets",
    "voiceover",
    "requirements",
    "examples",
]

BAD_WORDS = [
    "unpaid",
    "free work",
    "free sample",
    "exposure only",
]


def flatten_text(value):
    """Turn nested JSON into searchable text."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        return " ".join(flatten_text(x) for x in value)

    if isinstance(value, dict):
        return " ".join(
            flatten_text(v)
            for v in value.values()
        )

    return ""


def get_jobs():
    response = requests.get(
        API_URL,
        params={
            "limit": 100
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "video-job-scanner/1.0"
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    # Dealwork may wrap the list in different keys.
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["jobs", "data", "items", "results"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def find_money(text):
    values = []

    # $50 / $50.00
    for match in re.findall(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        text,
        flags=re.I
    ):
        values.append(float(match.replace(",", "")))

    # 50 USD / 50 USDC
    for match in re.findall(
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|USDC)",
        text,
        flags=re.I
    ):
        values.append(float(match.replace(",", "")))

    return values


def get_budget(job, text):
    possible_fields = [
        "budget",
        "budgetMin",
        "budgetMax",
        "price",
        "amount",
        "maxBudget",
    ]

    numbers = []

    for field in possible_fields:
        value = job.get(field)

        if isinstance(value, (int, float)):
            numbers.append(float(value))

        elif isinstance(value, str):
            numbers.extend(find_money(value))

    numbers.extend(find_money(text))

    return max(numbers) if numbers else 0


def count_videos(text):
    patterns = [
        r"(\d+)\s*(?:videos|reels|shorts)",
        r"(\d+)\s*(?:video|reel|short)",
    ]

    numbers = []

    for pattern in patterns:
        for match in re.findall(pattern, text):
            numbers.append(int(match))

    return max(numbers) if numbers else 1


def analyse_job(job):
    text = flatten_text(job).lower()

    video_hits = [
        word for word in VIDEO_WORDS
        if word in text
    ]

    recurring_hits = [
        word for word in RECURRING_WORDS
        if word in text
    ]

    brief_hits = [
        word for word in GOOD_BRIEF_WORDS
        if word in text
    ]

    bad_hits = [
        word for word in BAD_WORDS
        if word in text
    ]

    budget = get_budget(job, text)
    video_count = count_videos(text)

    score = 0

    # Must actually be video-related.
    if video_hits:
        score += 5

    # Recurring work is very valuable to us.
    if recurring_hits:
        score += 4

    if len(recurring_hits) >= 2:
        score += 2

    # Clear instructions make AI production easier.
    if len(brief_hits) >= 2:
        score += 3

    if len(brief_hits) >= 4:
        score += 2

    # Minimum target.
    if budget >= MIN_PRICE:
        score += 4

    # Multiple videos.
    if video_count >= 2:
        score += 3

    if video_count >= 5:
        score += 2

    # Remove suspicious/free work.
    if bad_hits:
        score -= 10

    # Require actual video language.
    if not video_hits:
        return None

    return {
        "score": score,
        "budget_found": budget,
        "video_count": video_count,
        "video_keywords": video_hits[:10],
        "recurring_keywords": recurring_hits[:10],
        "brief_keywords": brief_hits[:10],
        "warning_keywords": bad_hits[:10],
        "job": job,
    }


def main():
    print("VIDEO JOB SCANNER")
    print("=" * 50)

    try:
        jobs = get_jobs()
    except Exception as e:
        print("ERROR:", e)
        return

    print(f"Jobs received: {len(jobs)}")
    print()

    results = []

    for job in jobs:
        result = analyse_job(job)

        if result is not None:
            results.append(result)

    results.sort(
        key=lambda x: (
            x["score"],
            x["budget_found"],
            x["video_count"]
        ),
        reverse=True
    )

    qualified = []

    for result in results:

        # Our first conservative filter.
        if (
            result["score"] >= 10
            and result["budget_found"] >= MIN_PRICE
        ):
            qualified.append(result)

    print(f"Video-related jobs: {len(results)}")
    print(f"QUALIFIED JOBS: {len(qualified)}")
    print()

    for index, result in enumerate(qualified[:20], start=1):

        job = result["job"]

        title = (
            job.get("title")
            or job.get("name")
            or "Untitled job"
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
        print(f"#{index} {title}")
        print(f"ID: {job_id}")
        print(f"Budget found: ${result['budget_found']}")
        print(f"Videos detected: {result['video_count']}")
        print(f"Score: {result['score']}")
        print(f"URL: {url}")
        print(
            "Recurring:",
            ", ".join(result["recurring_keywords"])
        )
        print(
            "Brief:",
            ", ".join(result["brief_keywords"])
        )

    output = {
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "jobs_received": len(jobs),

        "video_related": len(results),

        "qualified": len(qualified),

        "matches": qualified[:20],
    }

    with open(
        "matches.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("Saved: matches.json")


if __name__ == "__main__":
    main()
