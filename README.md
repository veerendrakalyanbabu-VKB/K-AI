# K AI World Pulse

## Globe-first dashboard release

The new interface adds selectable earthquake, flight, marine, satellite, weather, air-quality, road-traffic and natural-event layers; searchable evidence; source coverage cards; a detail drawer; and a separate local-conditions panel. Camera support includes an opt-in phone sky view for approximate local bearings; official camera links remain available. Flights, vessels, and satellites remain bounded public snapshots with source and freshness labels.

**Read [actual coverage and operating limits](docs/DATA-COVERAGE.md) before presenting this as live intelligence.** Flights are quota-cached regional snapshots, satellites are calculated estimates, traffic is a single road sample, and marine reception covers an Indian Ocean sector. No fabricated counts or paid UI package is used.

Existing Render configuration is retained. Set the optional `AISSTREAM_API_KEY` and `TOMTOM_API_KEY` server environment variables, then deploy the latest commit. Keep one server worker. Never put keys into browser code. Free Render sleep interrupts marine streaming.

Run `python -m pytest -q` and `node --check app/static/app.js` to verify the release. The following original MVP notes remain for context.

**A zero-cost-first, source-grounded World State Engine prototype.**

K AI World Pulse makes live public signals understandable through an interactive global event map and a location incident brief. It is decision support only; it is **not** an official warning system.

## What works now

- Live global earthquake events from the USGS GeoJSON feed.
- Interactive map with source-linked event markers.
- Current weather brief for Hyderabad, Mumbai, Chennai, Bengaluru, Kolkata, or New Delhi.
- Transparent rule-based risk factors and human-reviewed next steps.
- Data timestamp, source cards, and clear safety disclaimer.

## Why this design

The MVP works without paid APIs, accounts, or model keys. A real LLM is intentionally not required for the first demo: source-grounded facts and deterministic safety logic are more reliable than an unverified chatbot.

NVIDIA NIM may be used later as an **optional development-time** provider through a server-side adapter. Its free Developer Program access is for prototyping/development/testing; it must not become the permanent production dependency. Never expose any key in browser JavaScript or commit it to Git.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Optional live connectors

Create a `.env` file in the project root. It is ignored by Git.

```env
AISSTREAM_API_KEY=your_private_key
TOMTOM_API_KEY=your_private_key
```

Restart Uvicorn after saving `.env`. TomTom traffic then appears in `/api/brief`. AISStream is configured server-side only; never expose its key in browser code.

## Test

```bash
pytest -q
```

## Data and licence posture

This prototype calls public endpoints directly and retains source links. Before any public deployment or commercial use, validate every provider's current terms, rate limits, attribution requirements, and redistribution rights. Do not scrape sources, bypass authentication, or represent K AI as an official government service.

## Next build milestones

1. Add India-specific official/authorised feeds only after access and terms are confirmed.
2. Add a provider-neutral, server-side LLM adapter with local-model fallback.
3. Add PostgreSQL/PostGIS world-state history, deduplication, and data-freshness monitoring.
4. Add RBAC, audit logs, review workflows, and a formal pilot evaluation pack.
