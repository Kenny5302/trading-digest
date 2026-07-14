"""
Portfolio Digest — turns a Robinhood-style positions CSV into a plain-English
daily portfolio summary using the Claude API.

Design decision: Python computes all math (totals, weights, movers) so numbers
are deterministic and verifiable. Claude is used only for what it is good at:
turning computed facts into a clear, readable narrative. The model is never
asked to do arithmetic.

Usage:
    python digest.py                    # reads positions.csv
    python digest.py my_positions.csv   # reads a specific file
"""

import os
import sys
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 1000
CONCENTRATION_FLAG_PCT = 25.0  # flag any single position above this weight

SYSTEM_PROMPT = """You are a portfolio digest writer for a personal trading journal.

Rules:
- You will receive pre-computed portfolio statistics. Use ONLY the numbers
  provided. Never invent, estimate, or recalculate figures.
- Write in plain English for the portfolio owner reviewing their own account.
- You are not a financial advisor. Never recommend buying or selling anything.
  You may point out facts worth the owner's attention (like concentration),
  but decisions belong to the owner.
- Be concise. No filler, no hype, no emojis.

Output exactly this structure in Markdown:

## Portfolio Snapshot
One short paragraph: total equity, overall tone of the portfolio today.

## Notable Positions
2-4 bullet points on the positions that most deserve attention
(largest weight, biggest gain, any position at a loss).

## Worth Reviewing
Exactly ONE observation the owner should think about, stated factually.
"""


def load_positions(path: str) -> pd.DataFrame:
    """Read a positions CSV and validate the expected columns exist."""
    required = {"symbol", "shares", "price", "average_cost", "total_return", "equity"}
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"CSV is missing required columns: {sorted(missing)}")
    return df


def compute_stats(df: pd.DataFrame) -> str:
    """Compute portfolio facts deterministically. Returns a text block for Claude."""
    total_equity = df["equity"].sum()
    df = df.copy()
    df["weight_pct"] = df["equity"] / total_equity * 100
    df["return_pct_of_cost"] = df.apply(
        lambda r: (r["total_return"] / (r["average_cost"] * r["shares"]) * 100)
        if r["average_cost"] * r["shares"] > 0 else 0.0,
        axis=1,
    )

    lines = [f"TOTAL PORTFOLIO EQUITY: ${total_equity:,.2f}",
             f"NUMBER OF POSITIONS: {len(df)}", "", "POSITIONS (sorted by weight):"]
    for _, r in df.sort_values("weight_pct", ascending=False).iterrows():
        lines.append(
            f"- {r['symbol']}: equity ${r['equity']:,.2f} "
            f"({r['weight_pct']:.1f}% of portfolio), "
            f"total return ${r['total_return']:,.2f} "
            f"({r['return_pct_of_cost']:+.1f}% on cost)"
        )

    flagged = df[df["weight_pct"] > CONCENTRATION_FLAG_PCT]
    if not flagged.empty:
        lines.append("")
        lines.append("CONCENTRATION FLAGS (position above "
                     f"{CONCENTRATION_FLAG_PCT:.0f}% of portfolio):")
        for _, r in flagged.iterrows():
            lines.append(f"- {r['symbol']} is {r['weight_pct']:.1f}% of the portfolio")

    losers = df[df["total_return"] < 0]
    if not losers.empty:
        lines.append("")
        lines.append("POSITIONS AT A LOSS:")
        for _, r in losers.iterrows():
            lines.append(f"- {r['symbol']}: ${r['total_return']:,.2f}")

    return "\n".join(lines)


def generate_digest(stats_block: str) -> str:
    """Send computed stats to Claude and return the narrative digest."""
    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Here are today's computed portfolio statistics "
                f"({date.today().isoformat()}):\n\n{stats_block}\n\n"
                "Write the digest."
            ),
        }],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "positions.csv"
    if not os.path.exists(csv_path):
        raise SystemExit(f"File not found: {csv_path}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Add it to a .env file.")

    df = load_positions(csv_path)
    stats = compute_stats(df)
    digest = generate_digest(stats)

    header = f"# Portfolio Digest — {date.today().isoformat()}\n\n"
    output = header + digest + "\n"
    print(output)

    os.makedirs("digests", exist_ok=True)
    out_path = os.path.join("digests", f"{date.today().isoformat()}.md")
    with open(out_path, "w") as f:
        f.write(output)
    print(f"[saved to {out_path}]")


if __name__ == "__main__":
    main()
