"""
Threads Post Generator
Reads today's top bet from bets.json and uses Claude to write
the morning bet post + evening result post template.
"""

import os
import json
import anthropic
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BETS_JSON         = "docs/data/bets.json"
POSTS_JSON        = "docs/data/posts.json"
TODAY             = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ── Load today's top bet ───────────────────────────────────────────────────────

def load_top_bet() -> dict | None:
    try:
        with open(BETS_JSON) as f:
            data = json.load(f)
        takes = [b for b in data.get("bets", []) if b.get("verdict") == "TAKE"]
        if not takes:
            return None
        # Best bet = highest confidence PERFECT or GOOD ladder fit
        perfect = [b for b in takes if b.get("ladder_fit") == "PERFECT"]
        return perfect[0] if perfect else takes[0]
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_ladder_state() -> dict:
    """Load current ladder state from history."""
    try:
        with open("docs/data/history.json") as f:
            history = json.load(f)
        # Find current attempt — count back to last loss or start
        attempt_bets = []
        for entry in reversed(history):
            if entry.get("result") == "loss":
                break
            attempt_bets.append(entry)
        attempt_bets.reverse()

        day_num   = len(attempt_bets) + 1
        balance   = 100.0
        for entry in attempt_bets:
            if entry.get("result") == "win":
                balance *= entry.get("odds_achieved", 2.0)

        return {
            "day_num":     day_num,
            "balance":     round(balance, 2),
            "attempt_num": 1,  # increment manually when tracking losses
        }
    except Exception:
        return {"day_num": 1, "balance": 100.0, "attempt_num": 1}


# ── Claude post generation ─────────────────────────────────────────────────────

MORNING_SYSTEM = """You write short, punchy, authentic sports betting posts for Threads (Meta).
Your tone is confident but not arrogant, transparent, and engaging.
You're running a "$100 to $102,400 in 10 days" ladder challenge — one bet per day at ~2x odds.

Rules:
- Max 300 characters for the hook line (Threads truncates)
- Total post under 500 characters  
- No emojis overload — 1-2 max, used purposefully
- Show the bet clearly: match, outcome, odds
- One-line reasoning — what's the edge
- State the stake and target
- End with a call to action (like if tailing, comment your pick, etc.)
- Sound like a real person, not a bot
- Never use hashtags
- Australian voice is fine (mate, arvo, etc. used sparingly)

Output ONLY the post text. No explanation, no quotes around it."""

EVENING_SYSTEM = """You write short, punchy result posts for a sports betting Threads account.
The account is running a "$100 to $102,400 ladder challenge" — transparent win or lose.

Rules:
- Under 400 characters total
- Direct and honest — celebrate wins, accept losses with dignity
- Update the balance clearly
- Tease tomorrow if a win
- If a loss, reset the ladder with confidence — no excuses
- 1-2 emojis max
- No hashtags
- Sound human, not robotic

Output ONLY the post text. No explanation, no quotes around it."""


def generate_morning_post(bet: dict, ladder: dict) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Write the morning bet post for today.

LADDER STATE:
- Day {ladder['day_num']} of the challenge
- Current balance: ${ladder['balance']}
- Target if this wins: ${round(ladder['balance'] * bet.get('odds', 2.0), 2)}

TODAY'S BET:
- Match: {bet.get('match')}
- Outcome: {bet.get('outcome')}  
- Odds: {bet.get('odds')}
- Market: {bet.get('market','').replace('_',' ')}
- Sport: {bet.get('sport')}
- Edge reasoning: {bet.get('reasoning','')}
- Confidence: {bet.get('confidence')}%
- Ladder fit: {bet.get('ladder_fit')}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=MORNING_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_evening_post(bet: dict, ladder: dict, result: str, actual_score: str = "") -> str:
    """result = 'win' or 'loss'"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    if result == "win":
        new_balance = round(ladder['balance'] * bet.get('odds', 2.0), 2)
        outcome_context = f"WON. New balance: ${new_balance}"
    else:
        outcome_context = f"LOST. Balance resets to $100. Starting attempt {ladder.get('attempt_num',1)+1} tomorrow."

    prompt = f"""Write the evening result post.

LADDER STATE:
- Was Day {ladder['day_num']}
- Starting balance was: ${ladder['balance']}

THE BET:
- {bet.get('match')} — {bet.get('outcome')} @ {bet.get('odds')}

RESULT: {outcome_context}
{f'Score: {actual_score}' if actual_score else ''}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=EVENING_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_skip_post(ladder: dict) -> str:
    """Post for days when there's no strong TAKE signal."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=MORNING_SYSTEM,
        messages=[{"role": "user", "content": f"""Write a post for today explaining we're skipping — 
no strong TAKE signal today and protecting the ${ladder['balance']} balance.
The ladder is on Day {ladder['day_num']}.
Discipline message — waiting for the right opportunity is part of the edge."""}],
    )
    return response.content[0].text.strip()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  THREADS POST GENERATOR  —  {TODAY}")
    print(f"{'='*55}\n")

    top_bet    = load_top_bet()
    ladder     = load_ladder_state()

    print(f"  Ladder state: Day {ladder['day_num']} | Balance: ${ladder['balance']}\n")

    posts = {
        "generated": TODAY,
        "ladder":    ladder,
        "bet":       top_bet,
        "posts":     {}
    }

    if not top_bet:
        print("  No TAKE signal today — generating skip post...")
        skip = generate_skip_post(ladder)
        posts["posts"]["morning"] = skip
        posts["posts"]["evening_win"]  = None
        posts["posts"]["evening_loss"] = None
        print(f"\n  SKIP POST:\n  {'─'*40}\n  {skip}\n")
    else:
        print(f"  Top bet: {top_bet.get('match')} — {top_bet.get('outcome')} @ {top_bet.get('odds')}")
        print(f"  Confidence: {top_bet.get('confidence')}% | Fit: {top_bet.get('ladder_fit')}\n")

        print("  Generating morning post...")
        morning = generate_morning_post(top_bet, ladder)

        print("  Generating evening win post...")
        eve_win = generate_evening_post(top_bet, ladder, "win")

        print("  Generating evening loss post...")
        eve_loss = generate_evening_post(top_bet, ladder, "loss")

        posts["posts"]["morning"]      = morning
        posts["posts"]["evening_win"]  = eve_win
        posts["posts"]["evening_loss"] = eve_loss

        print(f"\n  MORNING POST:\n  {'─'*40}\n  {morning}\n")
        print(f"\n  EVENING (WIN):\n  {'─'*40}\n  {eve_win}\n")
        print(f"\n  EVENING (LOSS):\n  {'─'*40}\n  {eve_loss}\n")

    os.makedirs("docs/data", exist_ok=True)
    with open(POSTS_JSON, "w") as f:
        json.dump(posts, f, indent=2)
    print(f"  Saved: {POSTS_JSON}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
