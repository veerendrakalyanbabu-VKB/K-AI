# World Pulse: globe release

## Globe refinement release

Small 18px SVG symbols now have a larger interaction target and a hover highlight; the size toggle enables 24px symbols. The globe adds a thinner atmosphere, terrain bump shading, damped controls, day/night static imagery, and an expanded view. Night imagery is an artistic basemap selection, not a real-time solar terminator or live Earth video. Reset/rotate correctly exit follow mode.

Aircraft registration and type codes appear when supplied. Departure, destination, ETA, photos, satellite owner/launch/status, phone AR, and complete worldwide movement coverage are **not implemented**. These require separately scoped data and device integrations. Do not present position snapshots as full FlightRadar24/MarineTraffic parity.

When Open-Meteo cannot serve weather, the server tries MET Norway Locationforecast with the application URL as its identifying User-Agent. Cached responses respect Expires and use If-Modified-Since. The closest forecast within one hour is returned with MET Norway attribution and a CC BY 4.0 link. Wind is converted from m/s to km/h; rainfall is forecast for the next hour. No rainfall value is inferred when missing. The cache lasts at least 30 minutes. Forecasts are not official alerts.

Verification: `node --test tests/controls.test.cjs` tests view toggles, zoom/rotation/reset, no-WebGL disabled controls, and safe detail rendering. Python tests cover forecast normalization and feed behavior. These are automated logic checks, not visual or exhaustive real-browser QA.

## Deployment access and follow controls

Live inspection on September 6 confirmed the Render marine bridge receiving reports and the ISS TLE fallback responding. The flight endpoint reported access denial; weather reported a quota error. These are provider failures, not evidence of zero activity.

An additional independent [adsb.fi public regional endpoint](https://github.com/adsbfi/opendata) is now tried when the other flight providers cannot return records. This source permits **personal, non-commercial use only**. Keep its in-app source link; obtain appropriate permission or remove this adapter before commercial/government operational use. It uses the public v3 radius endpoint, never the feeder-only global snapshot. A shared lock spaces calls more than one second apart; results cache for three minutes. No alternate IP, proxy or authentication bypass is used.

Icon budgets now reserve 50 for satellites, 200 for aircraft and 250 for vessels, avoiding vessel counts hiding the satellite icon. Additional records remain points. Click a record and choose **Follow incoming position updates** to keep the camera on its reported/estimated location as new snapshots arrive. No aircraft or vessel movement is invented between snapshots. Stop following restores manual navigation. Provider timestamps are retained, and AIS timestamps are normalized to ISO 8601 for browsers.

## Resilience and icon update

Aircraft, vessels and satellites use original SVG icon markers; up to 500 icons are drawn at once, with additional records drawn as points and retained in the list. Visual reference: [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view). No code, imagery or 3D assets were copied from that project.

Flights fall back to [adsb.lol](https://www.adsb.lol/docs/open-data/api/) when OpenSky has no usable response. Attribution: **adsb.lol contributors, ODbL 1.0**. The fallback covers 250 nautical miles around the selected city, caches for two minutes, and rejects positions older than 120 seconds at the provider snapshot time. It is a receiver-limited reported snapshot, not worldwide completeness. Data remains under ODbL, separate from this repository's code license.

When CelesTrak is unavailable, [Where the ISS at?](https://wheretheiss.at/w/developer) supplies an ISS-only TLE fallback. Its source is displayed in the drawer. Positions remain SGP4 estimates, and the same 14-day element age limit applies. No bundled old TLE or synthetic position is used to fill an outage.

AISStream now accepts PositionReport, StandardClassBPositionReport and ExtendedClassBPositionReport. Coverage includes the Indian Ocean/Singapore sector (0–30°N, 60–106°E), southern North Sea (50–54°N, 2°W–6°E) and Florida coast (24–31°N, 83–78°W). The same 1,500-record bound and ten-minute expiry apply. `diagnostics` reports counts and last received message time; a connected socket does not guarantee positioned vessels.

Temporary connection/time-out failures retry after five minutes. Quota/authentication errors retain conservative backoff, and CelesTrak retains its two-hour interval. These recovery changes do not guarantee upstream availability.

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
