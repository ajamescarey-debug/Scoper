"""
NBA Data Fetcher
Pulls real stats from BallDontLie (free) + NBA Stats API (free/unofficial)
for every NBA game in the next 24 hours.
Outputs: docs/data/nba_context.json
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

OUTPUT = "docs/data/nba_context.json"
TODAY  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

BDL_BASE  = "https://api.balldontlie.io/v1"
NBA_BASE  = "https://stats.nba.com/stats"

BDL_HEADERS = {"Authorization": os.environ.get("BALLDONTLIE_KEY", "")}

NBA_HEADERS = {
    "Host":             "stats.nba.com",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":           "application/json, text/plain, */*",
    "Accept-Language":  "en-US,en;q=0.9",
    "Accept-Encoding":  "gzip, deflate, br",
    "Connection":       "keep-alive",
    "Referer":          "https://www.nba.com/",
    "x-nba-stats-origin":"stats",
    "x-nba-stats-token": "true",
}

CURRENT_SEASON = "2025-26"


def bdl_get(endpoint: str, params: dict = {}) -> dict:
    try:
        r = requests.get(f"{BDL_BASE}/{endpoint}", headers=BDL_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [warn] BDL {endpoint}: {e}")
        return {"data": []}


def nba_get(endpoint: str, params: dict = {}) -> dict:
    try:
        r = requests.get(f"{NBA_BASE}/{endpoint}", headers=NBA_HEADERS, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [warn] NBA Stats {endpoint}: {e}")
        return {"resultSets": []}


def parse_nba_resultset(data: dict, set_name: str) -> list[dict]:
    """Convert NBA Stats API resultSet into list of dicts."""
    for rs in data.get("resultSets", []):
        if rs.get("name") == set_name:
            headers = rs.get("headers", [])
            rows    = rs.get("rowSet", [])
            return [dict(zip(headers, row)) for row in rows]
    return []


def fetch_games_today() -> list[dict]:
    """Get NBA games scheduled for today via BallDontLie."""
    data = bdl_get("games", {"dates[]": TODAY, "per_page": 30})
    games = []
    for g in data.get("data", []):
        home = g.get("home_team", {})
        away = g.get("visitor_team", {})
        games.append({
            "game_id":   g.get("id"),
            "status":    g.get("status"),
            "home":      home.get("full_name"),
            "away":      away.get("full_name"),
            "home_abbr": home.get("abbreviation"),
            "away_abbr": away.get("abbreviation"),
            "home_id":   home.get("id"),
            "away_id":   away.get("id"),
            "date":      g.get("date", TODAY)[:10],
            "season":    g.get("season"),
        })
    print(f"  [nba] Found {len(games)} games today")
    return games


def fetch_team_last_games(team_id: int, n: int = 10) -> list[dict]:
    """Last N game results for a team via BDL."""
    data = bdl_get("games", {
        "team_ids[]": team_id,
        "seasons[]":  2025,
        "per_page":   n,
        "sort":       "date",
        "order":      "desc",
    })
    results = []
    for g in data.get("data", []):
        home    = g.get("home_team", {})
        visitor = g.get("visitor_team", {})
        hs      = g.get("home_team_score", 0) or 0
        vs      = g.get("visitor_team_score", 0) or 0
        is_home = home.get("id") == team_id
        team_score = hs if is_home else vs
        opp_score  = vs if is_home else hs
        won        = team_score > opp_score
        opponent   = visitor.get("full_name") if is_home else home.get("full_name")
        results.append({
            "date":       g.get("date", "")[:10],
            "opponent":   opponent,
            "home_away":  "H" if is_home else "A",
            "score":      f"{team_score}-{opp_score}",
            "result":     "W" if won else "L",
            "margin":     team_score - opp_score,
        })
    return results


def fetch_team_season_stats(team_abbr: str) -> dict:
    """Advanced team stats from NBA Stats API — net rating, pace, ortg, drtg."""
    data = nba_get("leaguedashteamstats", {
        "Season":        CURRENT_SEASON,
        "SeasonType":    "Regular Season",
        "MeasureType":   "Advanced",
        "PerMode":       "PerGame",
        "PaceAdjust":    "N",
        "Rank":          "N",
        "PlusMinus":     "N",
        "Outcome":       "",
        "Location":      "",
        "Month":         "0",
        "SeasonSegment": "",
        "DateFrom":      "",
        "DateTo":        "",
        "OpponentTeamID":"0",
        "VsConference":  "",
        "VsDivision":    "",
        "GameSegment":   "",
        "Period":        "0",
        "LastNGames":    "0",
        "GameScope":     "",
        "PlayerExperience":"",
        "PlayerPosition":"",
        "StarterBench":  "",
        "DraftYear":     "",
        "DraftPick":     "",
        "College":       "",
        "Country":       "",
        "Height":        "",
        "Weight":        "",
        "Conference":    "",
        "Division":      "",
    })

    rows = parse_nba_resultset(data, "LeagueDashTeamStats")
    for row in rows:
        if row.get("TEAM_ABBREVIATION", "").upper() == team_abbr.upper():
            return {
                "net_rating":    round(row.get("NET_RATING", 0), 1),
                "off_rating":    round(row.get("OFF_RATING", 0), 1),
                "def_rating":    round(row.get("DEF_RATING", 0), 1),
                "pace":          round(row.get("PACE", 0), 1),
                "ts_pct":        round(row.get("TS_PCT", 0), 3),
                "ast_ratio":     round(row.get("AST_RATIO", 0), 1),
                "reb_pct":       round(row.get("REB_PCT", 0), 3),
                "wins":          row.get("W", 0),
                "losses":        row.get("L", 0),
            }
    return {}


def fetch_home_away_splits(team_abbr: str) -> dict:
    """Home vs away record and net rating splits."""
    results = {}
    for location in ("Home", "Road"):
        data = nba_get("leaguedashteamstats", {
            "Season":      CURRENT_SEASON,
            "SeasonType":  "Regular Season",
            "MeasureType": "Base",
            "PerMode":     "PerGame",
            "Location":    location,
            "LastNGames":  "0",
            "Month":       "0",
            "OpponentTeamID": "0",
            "PaceAdjust":  "N",
            "Rank":        "N",
            "PlusMinus":   "N",
            "Outcome":     "",
            "SeasonSegment":"",
            "DateFrom":    "",
            "DateTo":      "",
            "VsConference":"",
            "VsDivision":  "",
            "GameSegment": "",
            "Period":      "0",
        })
        rows = parse_nba_resultset(data, "LeagueDashTeamStats")
        for row in rows:
            if row.get("TEAM_ABBREVIATION", "").upper() == team_abbr.upper():
                results[location.lower()] = {
                    "w":         row.get("W", 0),
                    "l":         row.get("L", 0),
                    "pts":       round(row.get("PTS", 0), 1),
                    "pts_allow": round(row.get("OPP_PTS", 0) if "OPP_PTS" in row else 0, 1),
                    "plus_minus":round(row.get("PLUS_MINUS", 0), 1),
                }
                break
    return results


def check_back_to_back(team_id: int) -> bool:
    """Check if team played yesterday — back-to-back flag."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    data = bdl_get("games", {
        "team_ids[]": team_id,
        "dates[]":    yesterday,
        "per_page":   5,
    })
    return len(data.get("data", [])) > 0


def fetch_injuries_nba(team_abbr: str) -> list[dict]:
    """
    NBA injury reports — uses a public ESPN endpoint as NBA Stats
    doesn't expose injuries cleanly. Falls back gracefully.
    """
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_abbr.lower()}/injuries"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        injuries = []
        for item in data.get("injuries", [])[:6]:
            athlete = item.get("athlete", {})
            injuries.append({
                "name":   athlete.get("displayName", "Unknown"),
                "status": item.get("status", ""),
                "detail": item.get("details", {}).get("fantasyStatus", {}).get("description", ""),
            })
        return injuries
    except Exception:
        return []


def enrich_game(game: dict) -> dict:
    """Pull full context for a single NBA game."""
    home_abbr = game["home_abbr"]
    away_abbr = game["away_abbr"]
    home_id   = game["home_id"]
    away_id   = game["away_id"]

    print(f"    Enriching: {game['home']} vs {game['away']}...")

    home_recent    = fetch_team_last_games(home_id, 10)
    away_recent    = fetch_team_last_games(away_id, 10)
    home_stats     = fetch_team_season_stats(home_abbr)
    away_stats     = fetch_team_season_stats(away_abbr)
    home_splits    = fetch_home_away_splits(home_abbr)
    away_splits    = fetch_home_away_splits(away_abbr)
    home_b2b       = check_back_to_back(home_id)
    away_b2b       = check_back_to_back(away_id)
    home_injuries  = fetch_injuries_nba(home_abbr)
    away_injuries  = fetch_injuries_nba(away_abbr)

    # Compute last 10 ATS-like record (margin > spread proxy)
    def form_string(results: list[dict]) -> str:
        return "".join(r["result"] for r in results[:10])

    def avg_margin(results: list[dict]) -> float:
        if not results: return 0.0
        return round(sum(r["margin"] for r in results) / len(results), 1)

    return {
        **game,
        "home_recent":   home_recent,
        "away_recent":   away_recent,
        "home_form":     form_string(home_recent),
        "away_form":     form_string(away_recent),
        "home_avg_margin": avg_margin(home_recent),
        "away_avg_margin": avg_margin(away_recent),
        "home_season_stats":  home_stats,
        "away_season_stats":  away_stats,
        "home_splits":   home_splits,
        "away_splits":   away_splits,
        "home_b2b":      home_b2b,
        "away_b2b":      away_b2b,
        "home_injuries": home_injuries,
        "away_injuries": away_injuries,
    }


def main():
    print(f"\n{'='*55}")
    print(f"  NBA DATA FETCHER  —  {TODAY}")
    print(f"{'='*55}\n")

    os.makedirs("docs/data", exist_ok=True)

    games = fetch_games_today()
    if not games:
        print("  No NBA games today.")
        with open(OUTPUT, "w") as f:
            json.dump({"generated": TODAY, "games": []}, f, indent=2)
        return

    print(f"\n  Enriching {len(games)} games...")
    enriched = []
    for game in games:
        try:
            enriched.append(enrich_game(game))
        except Exception as e:
            print(f"  [warn] Failed {game.get('home')} vs {game.get('away')}: {e}")
            enriched.append(game)

    output = {
        "generated":  TODAY,
        "game_count": len(enriched),
        "games":      enriched,
    }
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  [done] Saved {len(enriched)} enriched games → {OUTPUT}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
