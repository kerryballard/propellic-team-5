"""
detection.py — Coiled Spring Opportunity Detection
Identifies clients where high search intent + temporary conversion dip
coincide with an external shock (weather, political, economic, news).
"""

import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field

# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class ExternalShock:
    shock_type: str           # 'weather', 'political', 'economic', 'news_event'
    description: str          # Human-readable description
    severity: float           # 0.0 - 1.0
    start_date: str
    location: str
    source: str               # Which API detected it

@dataclass
class CoiledSpringOpportunity:
    client_id: str
    client_name: str
    score: float              # 0-100 composite Coiled Spring score
    intent_score: float       # Search intent strength (0-100)
    conversion_dip_pct: float # % drop in conversion rate (negative = dip)
    shocks: list              # List of ExternalShock objects
    baseline_cvr: float       # Normal conversion rate
    current_cvr: float        # Current (depressed) conversion rate
    estimated_rebound_days: int
    recommendation: str       # Plain-English action for account manager
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Thresholds ────────────────────────────────────────────────────────────────

INTENT_THRESHOLD       = 60.0   # Minimum intent score to qualify
CONVERSION_DIP_MIN     = -0.10  # At least 10% drop in CVR
SHOCK_SEVERITY_MIN     = 0.3    # Minimum shock severity to count
COILED_SPRING_MIN      = 55.0   # Minimum composite score to surface opportunity


# ── Core Detection Logic ──────────────────────────────────────────────────────

def compute_intent_score(impressions_recent: float, impressions_baseline: float) -> float:
    """
    Score search intent 0-100 based on impression volume vs. baseline.
    High impressions = people are still searching = high intent.
    """
    if impressions_baseline <= 0:
        return 0.0
    ratio = impressions_recent / impressions_baseline
    # Scale: 1.0x baseline = 50, 1.5x = 75, 2x = 100, 0.5x = 25
    score = min(100.0, max(0.0, ratio * 50.0))
    return round(score, 1)


def compute_conversion_dip(current_cvr: float, baseline_cvr: float) -> float:
    """
    Returns % change in conversion rate. Negative = dip.
    e.g., -0.20 means 20% below baseline.
    """
    if baseline_cvr <= 0:
        return 0.0
    return round((current_cvr - baseline_cvr) / baseline_cvr, 4)


def compute_shock_score(shocks: list) -> float:
    """
    Combine multiple external shocks into a single severity score (0-1).
    Uses weighted average, capped at 1.0.
    """
    if not shocks:
        return 0.0
    total = sum(s.severity for s in shocks)
    return round(min(1.0, total / len(shocks) + (0.1 * (len(shocks) - 1))), 3)


def compute_coiled_spring_score(
    intent_score: float,
    conversion_dip_pct: float,
    shock_score: float
) -> float:
    """
    Composite Coiled Spring score (0-100).

    Formula:
    - Intent (40%): High intent = spring is loaded
    - Dip severity (35%): Bigger dip = bigger rebound opportunity
    - Shock score (25%): Confirmed external cause = confidence multiplier
    """
    dip_score = min(100.0, abs(conversion_dip_pct) * 400)  # 25% dip = 100
    shock_component = shock_score * 100

    score = (
        0.40 * intent_score +
        0.35 * dip_score +
        0.25 * shock_component
    )
    return round(min(100.0, score), 1)


def estimate_rebound_days(shocks: list, conversion_dip_pct: float) -> int:
    """
    Estimate how many days until conversion rates rebound.
    Based on shock type and dip severity.
    """
    base_days = {
        "weather": 5,
        "news_event": 7,
        "political": 14,
        "economic": 21,
    }
    if not shocks:
        return 10

    primary_shock = max(shocks, key=lambda s: s.severity)
    base = base_days.get(primary_shock.shock_type, 10)

    # Deeper dips take longer to recover
    dip_factor = 1 + abs(conversion_dip_pct)
    return round(base * dip_factor)


def generate_recommendation(opportunity: "CoiledSpringOpportunity") -> str:
    """
    Generate a plain-English recommendation for the account manager.
    """
    shock_labels = ", ".join(set(s.shock_type for s in opportunity.shocks))
    dip_pct = abs(round(opportunity.conversion_dip_pct * 100, 1))
    rebound = opportunity.estimated_rebound_days

    if opportunity.score >= 80:
        urgency = "STRONG BUY"
    elif opportunity.score >= 65:
        urgency = "RECOMMENDED"
    else:
        urgency = "MONITOR"

    return (
        f"[{urgency}] {opportunity.client_name} shows a {dip_pct}% conversion dip "
        f"driven by {shock_labels} — but search intent remains high. "
        f"Recommend maintaining or increasing spend now to capture market share. "
        f"Estimated rebound window: {rebound} days. "
        f"Competitors who cut spend will lose ground during recovery."
    )


# ── Main Detection Function ───────────────────────────────────────────────────

def detect_opportunities(clients_data: list, shocks_by_location: dict) -> list:
    """
    Main entry point. Takes client performance data and detected external shocks,
    returns a ranked list of CoiledSpring opportunities.

    Args:
        clients_data: List of dicts with keys:
            client_id, client_name, location,
            current_cvr, baseline_cvr,
            impressions_recent, impressions_baseline

        shocks_by_location: Dict of location -> list of ExternalShock objects

    Returns:
        List of CoiledSpringOpportunity, sorted by score descending
    """
    opportunities = []

    for client in clients_data:
        client_id       = client["client_id"]
        client_name     = client["client_name"]
        location        = client.get("location", "US")
        current_cvr     = client.get("current_cvr", 0)
        baseline_cvr    = client.get("baseline_cvr", 0)
        imp_recent      = client.get("impressions_recent", 0)
        imp_baseline    = client.get("impressions_baseline", 1)

        # Step 1: Calculate intent score
        intent_score = compute_intent_score(imp_recent, imp_baseline)

        # Step 2: Calculate conversion dip
        dip_pct = compute_conversion_dip(current_cvr, baseline_cvr)

        # Step 3: Get relevant external shocks for this client's location
        shocks = shocks_by_location.get(location, [])
        active_shocks = [s for s in shocks if s.severity >= SHOCK_SEVERITY_MIN]

        # Step 4: Filter — must meet all minimum thresholds
        if intent_score < INTENT_THRESHOLD:
            continue
        if dip_pct > CONVERSION_DIP_MIN:  # dip_pct is negative, so this filters small dips
            continue

        # Step 5: Compute composite score
        shock_score = compute_shock_score(active_shocks)
        cs_score = compute_coiled_spring_score(intent_score, dip_pct, shock_score)

        if cs_score < COILED_SPRING_MIN:
            continue

        # Step 6: Build opportunity object
        rebound_days = estimate_rebound_days(active_shocks, dip_pct)

        opp = CoiledSpringOpportunity(
            client_id=client_id,
            client_name=client_name,
            score=cs_score,
            intent_score=intent_score,
            conversion_dip_pct=dip_pct,
            shocks=active_shocks,
            baseline_cvr=baseline_cvr,
            current_cvr=current_cvr,
            estimated_rebound_days=rebound_days,
            recommendation=""
        )
        opp.recommendation = generate_recommendation(opp)
        opportunities.append(opp)

    # Sort by score descending
    return sorted(opportunities, key=lambda x: x.score, reverse=True)


# ── Quick Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Sample data to verify logic works
    sample_clients = [
        {
            "client_id": "client_001",
            "client_name": "Acme Roofing",
            "location": "Houston, TX",
            "current_cvr": 0.018,
            "baseline_cvr": 0.031,
            "impressions_recent": 45000,
            "impressions_baseline": 38000,
        },
        {
            "client_id": "client_002",
            "client_name": "Gulf Coast HVAC",
            "location": "Houston, TX",
            "current_cvr": 0.029,
            "baseline_cvr": 0.030,
            "impressions_recent": 12000,
            "impressions_baseline": 13000,
        },
    ]

    sample_shocks = {
        "Houston, TX": [
            ExternalShock(
                shock_type="weather",
                description="Hurricane Beryl aftermath — heavy flooding",
                severity=0.85,
                start_date="2024-07-08",
                location="Houston, TX",
                source="open_meteo"
            )
        ]
    }

    results = detect_opportunities(sample_clients, sample_shocks)

    print(f"\nFound {len(results)} Coiled Spring opportunities:\n")
    for opp in results:
        print(f"Client: {opp.client_name}")
        print(f"Score:  {opp.score}/100")
        print(f"Dip:    {round(opp.conversion_dip_pct * 100, 1)}%")
        print(f"Recommendation: {opp.recommendation}")
        print("-" * 60)
