# Portfolio Digest

Turns a Robinhood-style positions CSV into a plain-English daily portfolio
summary using the Claude API. Built as my first Claude API project: one focused
tool that does its job well.

## What it does

Give it your positions export, get back a short Markdown digest:

- **Portfolio Snapshot** — total equity and the overall picture
- **Notable Positions** — the holdings that deserve attention today
- **Worth Reviewing** — exactly one factual observation (e.g. a single
  position exceeding 25% of the portfolio)

Each digest is printed and saved to `digests/YYYY-MM-DD.md`, building a
reviewable journal over time.

## Design decisions

- **Python does the math, Claude does the writing.** Totals, weights, and
  return percentages are computed deterministically in pandas before the API
  call. The model is instructed to use only the provided numbers — LLMs are
  the wrong tool for arithmetic and the right tool for clear narrative.
- **A strict system prompt.** The digest has a fixed structure, a no-advice
  rule (it observes; it never recommends trades), and a no-invented-numbers
  rule.
- **Deliberately small scope.** One API call, no streaming, no agents. See
  Future Improvements for what was consciously deferred.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then paste your Anthropic API key into .env
```

## Usage

```bash
python digest.py                      # reads positions.csv
python digest.py sample_positions.csv # try it with the included sample
```

CSV columns expected: `symbol, shares, price, average_cost, total_return,
equity` (a `name` column is fine too — matches a Robinhood holdings layout).
Your real `positions.csv` is gitignored; only the fake sample ships with the
repo.

## Future improvements

- Pull live quotes (Finnhub) so the digest can compare against yesterday
- Historical diffing between digests ("what changed since last run")
- Prompt caching if the position list grows large
- Optional FastAPI endpoint to serve the digest to my Stock Helper extension

## Cost

A run on ~10 positions uses roughly a thousand tokens round-trip on Claude
Sonnet — a fraction of a cent per digest.
