"""Bounded, cached public feeds. Credentials never leave this process."""
import asyncio
import xml.etree.ElementTree as ET
import json
import math
import os
import random
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
import websockets
from fastapi import APIRouter, HTTPException
from app.weather import forecast
from app.osint import normalize_gdacs

router = APIRouter()
CITIES = {"Hyderabad": (17.385, 78.487), "Mumbai": (19.076, 72.878), "New Delhi": (28.614, 77.209), "Chennai": (13.083, 80.271), "Bengaluru": (12.972, 77.595), "Kolkata": (22.573, 88.364)}
cache, locks = {}, {}
vessels = {}
voyages = {}
request_counts = {}
marine_status = "not_configured"
marine_task = None
marine_diagnostics = {"messages": 0, "positions": 0, "last_message_at": None}
AIS_TYPES = ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport")


def ais_time(raw):
    if not isinstance(raw, str):
        return None
    try:
        text = re.sub(r" ([+-]\d{2})(\d{2}) UTC$", r"\1:\2", raw).replace(" ", "T", 1)
        return datetime.fromisoformat(text).isoformat()
    except ValueError:
        return None


async def fi_snapshot(city, lat, lon):
    # Separate provider, public regional endpoint; never use feeder-only endpoints.
    async with locks.setdefault("fi-rate", asyncio.Lock()):
        await asyncio.sleep(1.05)
        return await cached("fi:" + city, f"https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/250", 180)


def now():
    return datetime.now(timezone.utc).isoformat()


def position(lat, lon):
    return isinstance(lat, (float, int)) and isinstance(lon, (float, int)) and math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


async def cached(name, url, ttl, params=None, raw=False):
    async with locks.setdefault("cache-stripe:" + str(hash(name) % 64), asyncio.Lock()):
        entry = cache.get(name)
        if entry and time.monotonic() < entry[0]:
            return entry[1]
        day = datetime.now(timezone.utc).date().isoformat()
        host = urlsplit(url).hostname
        bucket = request_counts.get(host, (day, 0))
        count = bucket[1] if bucket[0] == day else 0
        limit = 300 if host == "opensky-network.org" else 2000
        if count >= limit:
            return {"status": "unavailable", "data": None, "reason": "Application daily request budget reached"}
        request_counts[host] = (day, count + 1)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.text if raw else response.json()
            result = {"status": "available", "fetched_at": now(), "data": data}
            delay = ttl
        except (httpx.HTTPError, ValueError) as exc:
            # No exception text: provider errors can contain query-string keys.
            result = {"status": "stale" if entry and entry[1].get("data") else "unavailable", "fetched_at": entry[1].get("fetched_at") if entry else None, "data": entry[1].get("data") if entry else None}
            code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            result["reason"] = {401: "Provider requires valid authentication", 403: "Provider denied access", 429: "Provider quota reached; waiting before retry"}.get(code, "Provider request failed; waiting before retry")
            if isinstance(exc, httpx.TimeoutException):
                result["reason"] = "Provider timed out"
            elif isinstance(exc, httpx.ConnectError):
                result["reason"] = "Provider connection failed"
            elif isinstance(exc, ValueError):
                result["reason"] = "Provider returned invalid JSON"
            delay = max(300, ttl) if code in (401, 403, 429) or "celestrak.org" in url else 300
        cache[name] = (time.monotonic() + delay, result)
        while len(cache) > 512:
            cache.pop(next(iter(cache)))
        return result


def ingest_vessel(message):
    if message.get("MessageType") == "ShipStaticData":
        report = message.get("Message", {}).get("ShipStaticData", {})
        mmsi = str(message.get("MetaData", {}).get("MMSI") or report.get("UserID") or "")
        if not mmsi or report.get("Valid") is False:
            return
        eta = report.get("Eta") or {}
        parts = [eta.get(k) for k in ("Month", "Day", "Hour", "Minute")]
        month_days = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        valid = all(isinstance(v, int) for v in parts) and 1 <= parts[0] <= 12 and 1 <= parts[1] <= month_days.get(parts[0], 0) and 0 <= parts[2] <= 23 and 0 <= parts[3] <= 59
        voyages[mmsi] = {"destination": str(report.get("Destination") or "").strip(" @") or None, "reported_eta": f"{parts[0]:02d}-{parts[1]:02d} {parts[2]:02d}:{parts[3]:02d} UTC (AIS omits year)" if valid else None, "imo": report.get("ImoNumber") or None, "voyage_reported_at": now(), "stored": time.monotonic()}
        while len(voyages) > 1500:
            voyages.pop(next(iter(voyages)))
        return
    if message.get("MessageType") not in AIS_TYPES:
        return
    meta = message.get("MetaData", {})
    report = message.get("Message", {}).get(message["MessageType"], {})
    lat, lon = meta.get("latitude", meta.get("Latitude")), meta.get("longitude", meta.get("Longitude"))
    if lat is None or lon is None:
        lat, lon = report.get("Latitude"), report.get("Longitude")
    if not position(lat, lon) or report.get("Valid") is False:
        return
    mmsi = str(meta.get("MMSI") or report.get("UserID") or "")
    if not mmsi:
        return
    marine_diagnostics["positions"] += 1
    if len(vessels) >= 1500 and mmsi not in vessels:
        vessels.pop(next(iter(vessels)))
    vessels[mmsi] = {"id": mmsi, "title": str(meta.get("ShipName") or mmsi).strip(), "lat": lat, "lng": lon, "speed_kn": report.get("Sog"), "heading": report.get("Cog"), "time": ais_time(meta.get("time_utc")), "received_at": now(), "received": time.monotonic(), "source": "AISStream", "url": "https://aisstream.io/", "layer": "marine"}


async def stream_marine():
    global marine_status
    key = os.getenv("AISSTREAM_API_KEY")
    if not key:
        return
    delay = 5
    while True:
        try:
            marine_status = "connecting"
            async with websockets.connect("wss://stream.aisstream.io/v0/stream", compression="deflate", max_size=1048576, ping_interval=20) as socket:
                await socket.send(json.dumps({"APIKey": key, "BoundingBoxes": [[[0, 60], [30, 106]], [[50, -2], [54, 6]], [[24, -83], [31, -78]]], "FilterMessageTypes": [*AIS_TYPES, "ShipStaticData"]}))
                async for raw in socket:
                    message = json.loads(raw)
                    marine_diagnostics["messages"] += 1
                    marine_diagnostics["last_message_at"] = now()
                    if "error" in message or "Error" in message:
                        marine_status = "provider_rejected"
                        return
                    if message.get("MessageType") == "SubscriptionConfirmation":
                        marine_status = "connected"
                        delay = 5
                    ingest_vessel(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            marine_status = "reconnecting"
        await asyncio.sleep(delay + random.random() * 3)
        delay = min(delay * 2, 300)


async def start():
    global marine_task
    marine_task = asyncio.create_task(stream_marine())


async def stop():
    if marine_task:
        marine_task.cancel()
        try:
            await marine_task
        except asyncio.CancelledError:
            pass


@router.get("/api/layers/{layer}")
async def layer_data(layer: str, city: str = "Hyderabad", latitude: float | None = None, longitude: float | None = None):
    if city not in CITIES:
        raise HTTPException(400, "Choose a supported city")
    lat, lon = CITIES[city]
    if latitude is not None or longitude is not None:
        if layer != "aviation" or not position(latitude, longitude):
            raise HTTPException(400, "Map coordinates require valid latitude/longitude and the aviation layer")
        lat, lon = round(latitude, 1), round(longitude, 1)
        city = f"Map area {lat}, {lon}"
    if layer == "osint":
        result = await cached("gdacs-rss", "https://www.gdacs.org/xml/rss.xml", 900, raw=True)
        try:
            items = normalize_gdacs(result.get("data"))
        except (ValueError, TypeError, ET.ParseError):
            # Malformed upstream XML is not an empty, healthy feed.
            return {"status": "unavailable", "items": [], "coverage": "GDACS feed unavailable or invalid. No disaster assessment inferred.", "reason": result.get("reason", "Invalid GeoRSS response")}
        return {**result, "data": None, "items": items, "coverage": "GDACS public disaster reports; feed window and coverage vary. Cached 15 minutes. Alert levels are source assessments, not a local-city warning.", "links": [{"title": "GDACS source and feed documentation", "url": "https://www.gdacs.org/feed_reference.aspx"}]}
    if layer == "marine":
        expired = [key for key, item in vessels.items() if time.monotonic() - item["received"] > 600]
        for key in expired:
            del vessels[key]
        for key in [k for k, v in voyages.items() if time.monotonic() - v["stored"] > 86400]:
            del voyages[key]
        for key, vessel in vessels.items():
            for field in ("destination", "reported_eta", "imo", "voyage_reported_at"):
                vessel[field] = voyages.get(key, {}).get(field)
        return {"status": marine_status, "diagnostics": dict(marine_diagnostics), "coverage": "Indian Ocean/Singapore sector (0–30°N, 60–106°E), southern North Sea (50–54°N, 2°W–6°E), Florida coast (24–31°N, 83–78°W). AIS Class A and B. Reports expire after 10 minutes; incomplete receiver coverage.", "items": [{k: v for k, v in item.items() if k != "received"} for item in vessels.values()]}
    if layer == "cams":
        return {"status": "links_only", "coverage": "Official viewing page; stream availability varies. No private cameras or synthetic camera markers.", "items": [], "links": [{"title": "NASA live · Earth and space broadcasts", "url": "https://www.nasa.gov/live/"}]}
    if layer == "starlink":
        result = await cached("starlink-omm", "https://celestrak.org/NORAD/elements/gp.php", 7200, {"GROUP": "STARLINK", "FORMAT": "JSON"})
        data = result.get("data")
        items = [{"title": row.get("OBJECT_NAME", "Starlink"), "omm": row, "source": "CelesTrak · Starlink SGP4 estimate", "url": "https://celestrak.org/NORAD/elements/"} for row in data[:1500] if isinstance(row, dict) and row.get("NORAD_CAT_ID")] if isinstance(data, list) else []
        status = result["status"] if items or result["status"] != "available" else "unavailable"
        return {**result, "status": status, "data": None, "items": items, "coverage": "Starlink OMM catalog, capped at 1,500 records per response. Elements cached two hours; calculated positions, not telemetry. Owner/launch date/operational status not verified by OMM.", "reason": result.get("reason") if status != "available" else None}
    if layer == "earth":
        result = await cached("earth", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson", 120)
        items = []
        for item in (result["data"] or {}).get("features", []):
            p, c = item.get("properties", {}), (item.get("geometry") or {}).get("coordinates", [])
            if len(c) < 2 or not position(c[1], c[0]):
                continue
            items.append({"id": item.get("id"), "title": f'M{p.get("mag")} · {p.get("place")}', "lat": c[1], "lng": c[0], "magnitude": p.get("mag"), "time": datetime.fromtimestamp(p["time"] / 1000, timezone.utc).isoformat() if p.get("time") else None, "url": p.get("url"), "source": "USGS", "layer": layer})
        return {**result, "data": None, "items": items, "coverage": "Reported global earthquakes · past hour; coverage and review levels vary."}
    if layer == "signals":
        result = await cached("signals", "https://eonet.gsfc.nasa.gov/api/v3/events", 900, {"status": "open", "limit": 50})
        items = []
        for event in (result["data"] or {}).get("events", []):
            geometry = event.get("geometry") or []
            if not geometry:
                continue
            g = geometry[-1]
            c = g.get("coordinates", [])
            if g.get("type") != "Point" or len(c) < 2 or not position(c[1], c[0]):
                continue
            items.append({"id": event["id"], "title": event["title"], "lat": c[1], "lng": c[0], "time": g.get("date"), "source": "NASA EONET", "url": event.get("link"), "layer": layer})
        return {**result, "data": None, "items": items, "coverage": "Up to 50 open NASA EONET natural events; last reported geometry, not live sensor positions."}
    if layer == "space":
        result = await cached("space", "https://celestrak.org/NORAD/elements/gp.php", 7200, {"GROUP": "stations", "FORMAT": "TLE"}, raw=True)
        lines = (result["data"] or "").splitlines()
        items = []
        for i in range(len(lines) - 2):
            if lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
                items.append({"title": lines[i].strip(), "tle1": lines[i + 1], "tle2": lines[i + 2]})
        if not items:
            fallback = await cached("iss-tle", "https://api.wheretheiss.at/v1/satellites/25544/tles", 7200)
            tle = fallback.get("data") or {}
            if str(tle.get("line1", "")).startswith("1 ") and str(tle.get("line2", "")).startswith("2 "):
                return {**fallback, "data": None, "items": [{"title": "ISS (ZARYA)", "tle1": tle["line1"], "tle2": tle["line2"], "source": "Where the ISS at? · SGP4 estimate", "url": "https://wheretheiss.at/w/developer"}], "coverage": "ISS-only fallback from Where the ISS at?; CelesTrak catalog unavailable. SGP4 calculated position, not live telemetry. Elements cached 2 hours."}
        return {**result, "data": None, "items": items, "status": result["status"] if items or result["status"] != "available" else "unavailable", "coverage": "Stations catalog only. SGP4 calculated positions, not live tracking. Elements cached 2 hours."}
    if layer == "aviation":
        result = await cached("aviation:" + city, "https://opensky-network.org/api/states/all", 1800, {"lamin": max(-90, lat - 1), "lamax": min(90, lat + 1), "lomin": max(-180, lon - 1), "lomax": min(180, lon + 1)})
        items = []
        for s in (result["data"] or {}).get("states") or []:
            if len(s) < 14 or not position(s[6], s[5]) or not s[3]:
                continue
            items.append({"id": s[0], "title": (s[1] or s[0]).strip(), "lat": s[6], "lng": s[5], "time": datetime.fromtimestamp(s[3], timezone.utc).isoformat(), "altitude_m": s[13] or s[7], "speed_ms": s[9], "source": "OpenSky", "url": "https://opensky-network.org/", "layer": layer})
        if not items or result["status"] != "available":
            fallback = await cached("adsb:" + city, f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/250", 120)
            planes = normalize_adsb(fallback.get("data") or {})
            if fallback["status"] == "available" and planes:
                return {**fallback, "data": None, "items": planes, "coverage": f"{city} · 250 nautical mile radius. adsb.lol contributors, ODbL 1.0. Reported positions cached 2 minutes; incomplete receiver coverage. OpenSky fallback."}
            if not items:
                alternate = await fi_snapshot(city, lat, lon)
                alternate_planes = normalize_adsb(alternate.get("data") or {}, source="adsb.fi · personal non-commercial data", source_url="https://adsb.fi/")
                if alternate["status"] == "available" and alternate_planes:
                    return {**alternate, "data": None, "items": alternate_planes, "coverage": f"{city} · 250 nautical mile radius, three-minute snapshots from adsb.fi. Personal non-commercial use only; incomplete receiver coverage.", "provider_checks": {"OpenSky": result["status"], "adsb.lol": fallback.get("reason", fallback["status"]), "adsb.fi": alternate["status"]}}
                fallback = {**fallback, "provider_checks": {"OpenSky": result.get("reason", result["status"]), "adsb.lol": fallback.get("reason", fallback["status"]), "adsb.fi": alternate.get("reason", alternate["status"])}}
                return {**fallback, "data": None, "items": planes, "coverage": f"{city} · OpenSky and adsb.lol checked. adsb.lol contributors, ODbL 1.0; regional coverage may be empty.", "reason": fallback.get("reason", "No positioned aircraft returned by either source")}
        return {**result, "data": None, "items": items, "coverage": f"{city} ±1° · reported aircraft positions, cached 30 min for anonymous quota. Limited receiver coverage; not continuous live flights."}
    if layer in ("weather", "air"):
        air = layer == "air"
        url = "https://air-quality-api.open-meteo.com/v1/air-quality" if air else "https://api.open-meteo.com/v1/forecast"
        result = await cached(layer + city, url, 900, {"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5,pm10" if air else "temperature_2m,wind_speed_10m,precipitation", "timezone": "UTC"})
        data = result["data"] or {}
        current = data.get("current", {})
        if not air and (result["status"] != "available" or not current):
            alternate = await forecast(city, lat, lon)
            if alternate.get("status") == "available":
                return alternate
        item = {"id": layer + city, "title": city + (" · Air quality" if air else " · Weather"), "lat": lat, "lng": lon, "time": current.get("time", "") + "Z" if current.get("time") else None, "metrics": current, "units": data.get("current_units", {}), "source": "Open-Meteo / CAMS" if air else "Open-Meteo", "url": "https://open-meteo.com/", "layer": layer}
        return {**result, "data": None, "items": [item] if current else [], "coverage": "Selected-city model estimate. US AQI, not Indian AQI." if air else "Selected-city weather model estimate; not an official warning feed."}
    if layer == "traffic":
        key = os.getenv("TOMTOM_API_KEY")
        if not key:
            return {"status": "not_configured", "items": [], "coverage": "Requires server-side TOMTOM_API_KEY."}
        result = await cached("traffic:" + city, "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json", 900, {"key": key, "point": f"{lat},{lon}", "unit": "KMPH"})
        flow = (result["data"] or {}).get("flowSegmentData", {})
        return {**result, "data": None, "coverage": "One road segment near the selected city center, refreshed at most every 15 min. Not city-wide congestion.", "items": [{"id": city + "traffic", "title": city + " · Road segment", "lat": lat, "lng": lon, "time": result["fetched_at"], "metrics": {k: flow.get(k) for k in ("currentSpeed", "freeFlowSpeed", "confidence", "roadClosure")}, "path": flow.get("coordinates", {}).get("coordinate", []), "source": "TomTom", "url": "https://www.tomtom.com/traffic-index/", "layer": layer}] if flow else []}
    raise HTTPException(404, "Unknown layer")


def normalize_adsb(data, source="adsb.lol contributors · ODbL 1.0", source_url="https://www.adsb.lol/docs/open-data/api/"):
    items = []
    timestamp = data.get("now")
    if not isinstance(timestamp, (int, float)):
        return items
    if timestamp > 100000000000:
        timestamp /= 1000
    for plane in (data.get("ac") or [])[:1000]:
        lat, lon = plane.get("lat"), plane.get("lon")
        age = plane.get("seen_pos")
        if not position(lat, lon) or not isinstance(age, (int, float)) or not 0 <= age <= 120:
            continue
        items.append({"id": plane.get("hex"), "title": str(plane.get("flight") or plane.get("r") or plane.get("hex") or "Aircraft").strip(), "registration": plane.get("r"), "aircraft_type": plane.get("t"), "lat": lat, "lng": lon, "heading": plane.get("track"), "altitude_ft": plane.get("alt_baro"), "speed_kn": plane.get("gs"), "time": datetime.fromtimestamp(timestamp - age, timezone.utc).isoformat(), "source": source, "url": source_url, "layer": "aviation"})
    return items
