# World Pulse: globe release

The dashboard is a working, limited-coverage public-data prototype, not a comprehensive real-time world model. It does not currently use an LLM. It never issues official alerts.

| Layer | Actual implementation | Refresh / limitations |
| --- | --- | --- |
| Earthquakes | USGS past-hour point events | Shared 2-minute cache; events are reported, not independently verified |
| Global signals | NASA EONET open event geometries | 15-minute cache, up to 50; not live sensors |
| Satellites | CelesTrak stations TLE, browser SGP4 | Elements cached 2 hours; estimated positions every 10 seconds; elements older than 14 days omitted |
| Flights | OpenSky anonymous state vectors near selected city | ±1° region, shared 30-minute cache; coverage, quotas and licensing apply, not continuous tracking |
| Marine | Server-side AISStream WebSocket, browser polls bounded snapshot | 0–30°N / 60–100°E, 1,500 vessels maximum, reports expire after 10 minutes; receiver gaps expected |
| Road traffic | TomTom flow segment near city center | Shared 15-minute cache, one segment, not city-wide congestion |
| Weather | Open-Meteo current model estimate | Six selectable Indian cities; 15-minute cache |
| Air | Open-Meteo / CAMS | US AQI and particulate model estimates, not Indian AQI or station readings |
| Cameras | NASA official public viewing page | Links only, not embedded globe camera streams; availability varies |

## Operations

Set `AISSTREAM_API_KEY` and `TOMTOM_API_KEY` in Render Environment. Never paste keys into frontend code or GitHub. Existing keys need not be changed. Run one Uvicorn worker: each process starts one upstream marine subscription and owns an in-memory cache. No database or paid dependency was added.

Render free instances can sleep. Marine ingestion stops while asleep; reports are not replayed or durably stored. Cache state resets on restart. Provider errors use backoff and expose no exception text containing keys. Repeated Refresh clicks reuse the shared cache. Failed caches remain unavailable/stale until the retry window. Coverage never implies global completeness.

Provider access is subject to terms, not a promise of perpetual free commercial use. Review [Open-Meteo terms](https://open-meteo.com/en/terms), [OpenSky](https://openskynetwork.github.io/opensky-api/rest.html), [AISStream documentation](https://aisstream.io/documentation), [CelesTrak policy](https://celestrak.org/NORAD/documentation/usage-policy.php), and your TomTom evaluation account before commercial deployment. Do not enable billing to activate this release.

## Verification

Run `python -m pytest -q`, `python -m compileall -q app`, and `node --check app/static/app.js`. Tests mock providers; they do not consume keys or quotas. Validate upstream availability separately on your deployment. Browser WebGL and the CDN libraries/textures must be accessible; if 3D fails, the evidence list remains usable. Globe imagery is a static basemap, not live satellite imagery.

## Interface

The interface uses a navy/amber globe-first layout, responsive panels, searchable records, accessible layer buttons, a keyboard-dismissable detail dialog, local model metrics, and a separate global watchlist. Reduced-motion preferences are respected; auto-rotation is off initially. Source dates and coverage are shown in each record drawer. Mobile layout places the globe first.

This release does not implement global camera ingestion, global live aircraft coverage, historical playback, sports, markets, or agent reasoning. Those remain future scoped integrations—not placeholder live counts.
