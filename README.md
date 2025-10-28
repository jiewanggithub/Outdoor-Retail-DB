# Outdoor Retail DB — Flask (No ORM)


Minimal Flask app for your course project. Uses **raw SQL strings** with SQLAlchemy connections (no ORM).


## Quickstart
1. Python 3.10+
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and set `DATABASEURI`
5. `python server.py` (or `flask run` if you prefer)


## What’s included
- List and create **Customers** (+ auto Accounts)
- Browse **Stores**, **Items**, **Inventory**
- Create **Orders** (one line item quick flow)
- Report: **Top items by units sold** (join + aggregation)


## Notes
- All DB calls use `engine.begin()` + `text()` and parameter binding to avoid SQL injection.
- No ORMs per course policy.
- Extend with more pages to cover every entity/relationship from your E/R.