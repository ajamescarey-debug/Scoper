"""
Football Data Fetcher
Pulls real stats from API-Football for every fixture in the next 24 hours.
Outputs: docs/data/football_context.json
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY   = os.environ["API_FOOTBALL_KEY"]
BASE_URL  = "https://v3.football.api-sports.io"
HEADERS   = {"x-apisports-key": API_KEY}
OUTPUT    = "docs/data/football_context.json"
TODAY     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
TOMORROW  = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

# Leagues we care about — ID: Name
LEAGUES = {
    39:  "EPL",
    140: "La Liga",
    135: "Serie A",
    78:  "Bundesliga",
    61:  "Ligue 1",
    2:   "Champions League",
    3:   "Europa League",
}

SEASON = 2025  # current season

def get(endpoint: str, params: dict) -> dict:
    """Single API call with error handling."""
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [warn] {endpoint} {params}: {e}")
        return {"response": []}


def fetch_fixtures_today() -> list[dict]:
    """Get all fixtures in next 24 hours across our leagues."""
    fixtures = []
    for league_id, league_name in LEAGUES.items():
        data = get("fixtures", {"league": league_id, "season": SEASON, "date": TODAY})
        for f in data.get("response", []):
            fixture = f.get("fixture", {})
            teams   = f.get("teams", {})
            status  = fixture.get("status", {}).get("short", "")

            if status not in ("NS", "TBD"):
                continue

            ts = fixture.get("timestamp", 0)
            game_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if game_dt > datetime.now(timezone.utc) + timedelta(hours=24):
                continue

            fixtures.append({
                "fixture_id": fixture.get("id"),
                "league_id":  league_id,
                "league":     league_name,
                "home_id":    teams.get("home", {}).get("id"),
                "away_id":    teams.get("away", {}).get("id"),
                "home":       teams.get("home", {}).get("name"),
                "away":       teams.get("away", {}).get("name"),
                "kickoff":    fixture.get("date"),
                "venue":      fixture.get("venue", {}).get("name", ""),
            })

    print(f"  [fixtures] Found {len(fixtures)} fixtures in next 24h")
    return fixtures


def fetch_team_form(team_id: int, league_id: int) -> dict:
    """Last 5 results, goals, xG for a team."""
    data = get("fixtures", {
        "team": team_id, "league": league_id,
        "season": SEASON, "last": 5, "status": "FT"
    })

    results = []
    goals_scored = []
    goals_conceded = []

    for f in data.get("response", []):
        teams   = f.get("teams", {})
        goals   = f.get("goals", {})
        score   = f.get("score", {}).get("fulltime", {})
        is_home = teams.get("home", {}).get("id") == team_id

        home_goals = score.get("home") or 0
        away_goals = score.get("away") or 0

        if is_home:
            scored    = home_goals
            conceded  = away_goals
            won       = teams.get("home", {}).get("winner")
        else:
            scored    = away_goals
            conceded  = home_goals
            won       = teams.get("away", {}).get("winner")

        result = "W" if won else ("L" if won is False else "D")
        results.append(result)
        goals_scored.append(scored)
        goals_conceded.append(conceded)

    avg_scored   = round(sum(goals_scored) / max(len(goals_scored), 1), 2)
    avg_conceded = round(sum(goals_conceded) / max(len(goals_conceded), 1), 2)
    form_string  = "".join(results)

    return {
        "form":          form_string,
        "results":       results,
        "goals_scored":  goals_scored,
        "goals_conceded":goals_conceded,
        "avg_scored":    avg_scored,
        "avg_conceded":  avg_conceded,
        "clean_sheets":  sum(1 for g in goals_conceded if g == 0),
        "btts_count":    sum(1 for s, c in zip(goals_scored, goals_conceded) if s > 0 and c > 0),
    }


def fetch_h2h(home_id: int, away_id: int) -> dict:
    """Last 5 H2H meetings."""
    data = get("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": 5})

    meetings = []
    over25_count = 0
    btts_count = 0

    for f in data.get("response", []):
        teams = f.get("teams", {})
        score = f.get("score", {}).get("fulltime", {})
        hg = score.get("home") or 0
        ag = score.get("away") or 0
        total = hg + ag

        winner = "home" if teams.get("home", {}).get("winner") else \
                 "away" if teams.get("away", {}).get("winner") else "draw"

        meetings.append({
            "home":   teams.get("home", {}).get("name"),
            "away":   teams.get("away", {}).get("name"),
            "score":  f"{hg}-{ag}",
            "total":  total,
            "winner": winner,
        })
        if total > 2.5: over25_count += 1
        if hg > 0 and ag > 0: btts_count += 1

    return {
        "meetings":    meetings,
        "over25_rate": f"{over25_count}/{len(meetings)}",
        "btts_rate":   f"{btts_count}/{len(meetings)}",
        "total_games": len(meetings),
    }


def fetch_injuries(team_id: int, league_id: int) -> list[dict]:
    """Current injuries and suspensions."""
    data = get("injuries", {"team": team_id, "league": league_id, "season": SEASON})
    injured = []
    for p in data.get("response", []):
        player = p.get("player", {})
        reason = p.get("reason", {})
        injured.append({
            "name":   player.get("name"),
            "type":   reason.get("type", "Unknown"),
            "reason": reason.get("reason", ""),
        })
    return injured[:8]  # cap at 8


def fetch_standings(league_id: int) -> list[dict]:
    """Current league standings — top 6 + bottom 3."""
    data = get("standings", {"league": league_id, "season": SEASON})
    standings = []
    try:
        table = data["response"][0]["league"]["standings"][0]
        for entry in table:
            standings.append({
                "rank":   entry.get("rank"),
                "team":   entry.get("team", {}).get("name"),
                "team_id":entry.get("team", {}).get("id"),
                "points": entry.get("points"),
                "gd":     entry.get("goalsDiff"),
                "form":   entry.get("form", ""),
                "played": entry.get("all", {}).get("played", 0),
            })
    except (IndexError, KeyError):
        pass
    return standings


def fetch_fixture_stats(fixture_id: int) -> dict:
    """xG and other stats if available (for recently played games used in form context)."""
    data = get("fixtures/statistics", {"fixture": fixture_id})
    xg = {}
    for team_stats in data.get("response", []):
        team_name = team_stats.get("team", {}).get("name", "")
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "expected_goals":
                xg[team_name] = stat.get("value", "N/A")
    return {"xg": xg}


def enrich_fixture(fix: dict, standings: dict) -> dict:
    """
    Pull context for a single fixture.
    Free tier = 100 req/day so we prioritise: form (2 calls) + H2H (1 call) = 3 per fixture.
    Injuries and standings only if requests remain.
    """
    home_id   = fix["home_id"]
    away_id   = fix["away_id"]
    league_id = fix["league_id"]

    print(f"    Enriching: {fix['home']} vs {fix['away']}...")

    home_form = fetch_team_form(home_id, league_id)
    away_form = fetch_team_form(away_id, league_id)
    h2h       = fetch_h2h(home_id, away_id)

    league_table  = standings.get(league_id, [])
    home_standing = next((s for s in league_table if s["team_id"] == home_id), {})
    away_standing = next((s for s in league_table if s["team_id"] == away_id), {})

    return {
        **fix,
        "home_form":     home_form,
        "away_form":     away_form,
        "h2h":           h2h,
        "home_injuries": [],
        "away_injuries": [],
        "home_standing": home_standing,
        "away_standing": away_standing,
    }


def main():
    print(f"\n{'='*55}")
    print(f"  FOOTBALL DATA FETCHER  —  {TODAY}")
    print(f"{'='*55}\n")

    os.makedirs("docs/data", exist_ok=True)

    # 1. Get today's fixtures
    fixtures = fetch_fixtures_today()
    if not fixtures:
        print("  No fixtures today. Saving empty context.")
        with open(OUTPUT, "w") as f:
            json.dump({"generated": TODAY, "fixtures": []}, f, indent=2)
        return

    # 2. Pre-fetch standings (1 req per league)
    print("  Fetching standings...")
    standings = {}
    league_ids = list(set(f["league_id"] for f in fixtures))
    for lid in league_ids:
        standings[lid] = fetch_standings(lid)

    # 3. Cap to 5 fixtures on free tier (3 req each = 15 req + 7 league calls = ~22 total)
    # Remove this cap once on paid plan
    MAX_FIXTURES = 5
    if len(fixtures) > MAX_FIXTURES:
        print(f"  [free tier] Capping to {MAX_FIXTURES} fixtures to stay under 100 req/day")
        fixtures = fixtures[:MAX_FIXTURES]

    # 4. Enrich each fixture
    print(f"\n  Enriching {len(fixtures)} fixtures...")
    enriched = []
    for fix in fixtures:
        try:
            enriched.append(enrich_fixture(fix, standings))
        except Exception as e:
            print(f"  [warn] Failed to enrich {fix.get('home')} vs {fix.get('away')}: {e}")
            enriched.append(fix)

    # 4. Save
    output = {
        "generated": TODAY,
        "fixture_count": len(enriched),
        "fixtures": enriched,
    }
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  [done] Saved {len(enriched)} enriched fixtures → {OUTPUT}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
