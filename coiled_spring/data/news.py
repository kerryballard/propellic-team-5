"""
news.py — NewsAPI Political & News Shock Detection
Pulls real-time news headlines and detects events that could
cause temporary conversion dips (political instability, major events, etc.)
Requires NEWS_API_KEY in environment or .env file.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"
TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"

# Keywords that signal potential conversion-impacting events
SHOCK_KEYWORDS = {
    "political": [
        "election", "protest", "riot", "government shutdown", "martial law",
        "political crisis", "coup", "sanctions", "tariff", "trade war",
        "civil unrest", "strike", "boycott"
    ],
    "economic": [
        "recession", "inflation spike", "interest rate hike", "market crash",
        "bank failure", "layoffs", "unemployment surge", "supply chain",
        "cost of living", "economic crisis"
    ],
    "weather": [
        "hurricane", "tornado", "flood", "wildfire", "blizzard",
        "earthquake", "tsunami", "evacuation", "state of emergency",
        "natural disaster", "storm damage"
    ],
    "news_event": [
        "shooting", "terrorist", "attack", "pandemic", "outbreak",
        "public health emergency", "major accident", "explosion"
    ]
}

# Severity weights per category
CATEGORY_SEVERITY = {
    "political": 0.55,
    "economic": 0.60,
    "weather": 0.70,
    "news_event": 0.65,
}


def get_news_shocks(location: str, days_back: int = 7) -> list:
    """
    Search NewsAPI for shock events in a given location over the past N days.
    Returns list of shock dicts compatible with the detection engine.

    Args:
        location: City/region string e.g. "Houston, TX" or "Miami"
        days_back: How many days back to search
    """
    if not NEWS_API_KEY:
        print("Warning: NEWS_API_KEY not set. Skipping news shocks.")
        return []

    from_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
    city = location.split(",")[0].strip()  # Extract city name

    all_shocks = []

    for category, keywords in SHOCK_KEYWORDS.items():
        query = f"({city}) AND ({' OR '.join(keywords[:5])})"

        try:
            resp = requests.get(NEWS_API_URL, params={
                "q": query,
                "from": from_date,
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY
            }, timeout=10)

            if resp.status_code != 200:
                continue

            articles = resp.json().get("articles", [])

            for article in articles:
                severity = compute_news_severity(article, category)
                if severity < 0.3:
                    continue

                all_shocks.append({
                    "shock_type": category,
                    "description": article.get("title", "Unknown event"),
                    "severity": severity,
                    "start_date": article.get("publishedAt", "")[:10],
                    "location": location,
                    "source": "newsapi",
                    "details": {
                        "url": article.get("url"),
                        "source": article.get("source", {}).get("name"),
                        "description": article.get("description", "")[:200]
                    }
                })

        except Exception as e:
            print(f"NewsAPI error for {category}: {e}")
            continue

    # Deduplicate and sort by severity
    seen = set()
    unique_shocks = []
    for shock in sorted(all_shocks, key=lambda x: x["severity"], reverse=True):
        key = shock["description"][:50]
        if key not in seen:
            seen.add(key)
            unique_shocks.append(shock)

    return unique_shocks


def compute_news_severity(article: dict, category: str) -> float:
    """
    Estimate severity of a news event based on keywords in title/description.
    Returns 0.0–1.0.
    """
    base = CATEGORY_SEVERITY.get(category, 0.5)
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    text = title + " " + description

    # Boost for high-severity language
    high_severity_words = [
        "emergency", "crisis", "devastat", "catastroph", "mass",
        "major", "severe", "critical", "widespread", "historic"
    ]
    boost = sum(0.05 for word in high_severity_words if word in text)

    return round(min(1.0, base + boost), 3)


def get_top_headlines_by_country(country: str = "us") -> list:
    """
    Get current top headlines for broad national shock detection.
    Useful for catching national-level events.
    """
    if not NEWS_API_KEY:
        return []

    try:
        resp = requests.get(TOP_HEADLINES_URL, params={
            "country": country,
            "pageSize": 20,
            "apiKey": NEWS_API_KEY
        }, timeout=10)

        if resp.status_code != 200:
            return []

        articles = resp.json().get("articles", [])
        flagged = []

        for article in articles:
            title = (article.get("title") or "").lower()
            for category, keywords in SHOCK_KEYWORDS.items():
                if any(kw.lower() in title for kw in keywords):
                    flagged.append({
                        "shock_type": category,
                        "description": article.get("title"),
                        "severity": CATEGORY_SEVERITY.get(category, 0.5),
                        "start_date": article.get("publishedAt", "")[:10],
                        "location": country.upper(),
                        "source": "newsapi_headlines",
                        "details": {"url": article.get("url")}
                    })
                    break

        return flagged

    except Exception as e:
        print(f"Headlines error: {e}")
        return []


if __name__ == "__main__":
    test_location = "Houston, TX"
    print(f"Fetching news shocks for: {test_location}\n")

    shocks = get_news_shocks(test_location, days_back=7)
    print(f"Found {len(shocks)} news shocks:\n")
    for s in shocks:
        print(f"  [{s['shock_type'].upper()}] {s['description'][:80]}")
        print(f"  Severity: {s['severity']} | Date: {s['start_date']}")
        print()

    print("Fetching national headlines...\n")
    headlines = get_top_headlines_by_country("us")
    print(f"Flagged {len(headlines)} national shock headlines")
