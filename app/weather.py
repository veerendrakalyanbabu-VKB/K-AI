"""MET Norway forecast fallback, with identifying UA and conditional caching."""
import asyncio
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

entries, locks = {}, {}
URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
UA = "KAIWorldPulse/0.3 https://github.com/veerendrakalyanbabu-VKB/K-AI"


async def forecast(city, lat, lon):
    async with locks.setdefault(city, asyncio.Lock()):
        old = entries.get(city, {})
        if time.monotonic() < old.get("retry", 0):
            return old.get("result", {})
        headers = {"User-Agent": UA}
        if old.get("modified"):
            headers["If-Modified-Since"] = old["modified"]
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(URL, params={"lat": round(lat, 4), "lon": round(lon, 4)}, headers=headers)
            if response.status_code == 304 and old.get("payload"):
                payload = old["payload"]
            else:
                response.raise_for_status()
                payload = response.json()
            result = normalize(payload, city, lat, lon)
            delay = 1800
            try:
                delay = max(delay, parsedate_to_datetime(response.headers["Expires"]).timestamp() - time.time())
            except (KeyError, TypeError, ValueError):
                pass
            entries[city] = {"retry": time.monotonic() + delay, "result": result, "payload": payload, "modified": response.headers.get("Last-Modified", old.get("modified"))}
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            result = {"status": "unavailable", "items": [], "coverage": "MET Norway forecast fallback unavailable; no conditions inferred."}
            entries[city] = {**old, "retry": time.monotonic() + 1800, "result": result}
        return result


def normalize(payload, city, lat, lon, timestamp=None):
    timestamp = time.time() if timestamp is None else timestamp
    candidates = []
    for row in payload.get("properties", {}).get("timeseries", []):
        try:
            delta = abs(datetime.fromisoformat(row["time"].replace("Z", "+00:00")).timestamp() - timestamp)
            if delta <= 3600:
                candidates.append((delta, row))
        except (KeyError, TypeError, ValueError):
            continue
    if not candidates:
        return {"status": "unavailable", "items": [], "coverage": "No MET Norway forecast valid within one hour of now."}
    row = min(candidates, key=lambda x: x[0])[1]
    data = row.get("data", {})
    details = data.get("instant", {}).get("details", {})
    wind = details.get("wind_speed")
    metrics = {"temperature_2m": details.get("air_temperature"), "wind_speed_10m": round(wind * 3.6, 1) if isinstance(wind, (float, int)) else None, "precipitation": data.get("next_1_hours", {}).get("details", {}).get("precipitation_amount")}
    item = {"id": "weather" + city, "title": city + " · Weather forecast", "lat": lat, "lng": lon, "time": row["time"], "metrics": metrics, "units": {"temperature_2m": "°C", "wind_speed_10m": "km/h", "precipitation": "mm / next hour"}, "source": "MET Norway · CC BY 4.0", "url": "https://api.met.no/", "license_url": "https://creativecommons.org/licenses/by/4.0/", "layer": "weather"}
    return {"status": "available", "fetched_at": datetime.now(timezone.utc).isoformat(), "items": [item], "coverage": "MET Norway Locationforecast, CC BY 4.0. Nearest forecast within one hour; wind converted from m/s to km/h. Rain is next-hour forecast, not observed rainfall."}
