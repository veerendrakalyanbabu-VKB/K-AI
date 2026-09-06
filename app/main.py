from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
load_dotenv(APP_DIR.parent / ".env")

app = FastAPI(title="K AI World Pulse", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# These feeds are deliberately key-free for a small prototype. They are not an
# official alerting channel and must not be used to issue public warnings.
USGS_QUAKES = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
NASA_EONET = "https://eonet.gsfc.nasa.gov/api/v3/events"
CELESTRAK_STATIONS = "https://celestrak.org/NORAD/elements/gp.php?GROUP=STATIONS&FORMAT=JSON"
TOMTOM_FLOW = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

CITY_COORDINATES = {
    "hyderabad": (17.3850, 78.4867),
    "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "chennai": (13.0827, 80.2707),
    "bengaluru": (12.9716, 77.5946),
    "kolkata": (22.5726, 88.3639),
}


async def fetch_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def quake_feature(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties", {})
    longitude, latitude, depth = feature.get("geometry", {}).get("coordinates", [None, None, None])
    return {
        "id": feature.get("id"),
        "place": properties.get("place", "Unknown location"),
        "magnitude": properties.get("mag"),
        "time": datetime.fromtimestamp(properties.get("time", 0) / 1000, tz=UTC).isoformat(),
        "url": properties.get("url"),
        "coordinates": {"latitude": latitude, "longitude": longitude, "depth_km": depth},
        "source": "USGS Earthquake Hazards Program",
    }


async def get_world_state() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "KAIWorldPulse/0.1"}) as client:
        try:
            quake_data = await fetch_json(client, USGS_QUAKES)
            quakes = [quake_feature(item) for item in quake_data.get("features", [])]
            status = "live"
        except (httpx.HTTPError, ValueError):
            quakes = []
            status = "unavailable"
        try:
            eonet_data = await fetch_json(client, NASA_EONET, {"status": "open", "limit": 20})
            natural_events = [{"id": e.get("id"), "title": e.get("title"), "categories": [c.get("title") for c in e.get("categories", [])], "date": e.get("geometry", [{}])[-1].get("date"), "source": "NASA EONET"} for e in eonet_data.get("events", [])]
        except (httpx.HTTPError, ValueError, IndexError):
            natural_events = []
        try:
            satellites = await fetch_json(client, CELESTRAK_STATIONS)
            station_count = len(satellites) if isinstance(satellites, list) else 0
        except (httpx.HTTPError, ValueError):
            station_count = 0

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "earthquakes": quakes,
        "natural_events": natural_events,
        "space": {"station_catalog_count": station_count, "source": "CelesTrak public GP data"},
        "sources": [
            {
                "name": "USGS Earthquake Hazards Program",
                "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php",
                "purpose": "Global earthquake events from the past hour",
                "official": True,
            },
            {"name": "NASA EONET", "url": "https://eonet.gsfc.nasa.gov/api/v3/events", "purpose": "Open natural-event metadata", "official": True},
            {"name": "CelesTrak", "url": "https://celestrak.org/NORAD/elements/", "purpose": "Public satellite catalog data", "official": False},
            {
                "name": "Open-Meteo",
                "url": "https://open-meteo.com/",
                "purpose": "Weather conditions for selected locations",
                "official": False,
            },
        ],
        "disclaimer": "K AI World Pulse is a decision-support prototype, not an official warning authority. Always follow local government and emergency-agency instructions.",
    }


async def get_weather(city: str) -> dict[str, Any]:
    normalized = city.strip().lower()
    if normalized not in CITY_COORDINATES:
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city}. Try Hyderabad, Mumbai, Chennai, Bengaluru, Kolkata, or New Delhi.")
    latitude, longitude = CITY_COORDINATES[normalized]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "KAIWorldPulse/0.1"}) as client:
        try:
            data = await fetch_json(client, OPEN_METEO, params)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Weather source temporarily unavailable.") from exc
    return {"city": city.title(), "coordinates": {"latitude": latitude, "longitude": longitude}, "current": data.get("current", {}), "units": data.get("current_units", {}), "source": "Open-Meteo", "source_url": "https://open-meteo.com/"}


async def get_air_quality(city: str) -> dict[str, Any]:
    normalized = city.strip().lower()
    if normalized not in CITY_COORDINATES:
        raise HTTPException(status_code=400, detail="Unsupported city")
    latitude, longitude = CITY_COORDINATES[normalized]
    params = {"latitude": latitude, "longitude": longitude, "current": "us_aqi,pm2_5,pm10,nitrogen_dioxide", "timezone": "auto"}
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "KAIWorldPulse/0.1"}) as client:
        try:
            data = await fetch_json(client, OPEN_METEO_AIR, params)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Air-quality source temporarily unavailable.") from exc
    return {"current": data.get("current", {}), "units": data.get("current_units", {}), "source": "Open-Meteo Air Quality"}


async def get_traffic(city: str) -> dict[str, Any]:
    key = os.getenv("TOMTOM_API_KEY")
    if not key:
        return {"status": "not_configured", "source": "TomTom Traffic"}
    latitude, longitude = CITY_COORDINATES[city.strip().lower()]
    params = {"key": key, "point": f"{latitude},{longitude}", "unit": "KMPH"}
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "KAIWorldPulse/0.1"}) as client:
        try:
            data = await fetch_json(client, TOMTOM_FLOW, params)
            flow = data.get("flowSegmentData", {})
            return {"status": "live", "current_speed_kph": flow.get("currentSpeed"), "free_flow_speed_kph": flow.get("freeFlowSpeed"), "confidence": flow.get("confidence"), "road_closure": flow.get("roadClosure"), "source": "TomTom Traffic"}
        except httpx.HTTPError:
            return {"status": "unavailable", "source": "TomTom Traffic"}


def risk_label(weather: dict[str, Any], quakes: list[dict[str, Any]]) -> tuple[str, list[str]]:
    current = weather["current"]
    risks: list[str] = []
    temperature = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    precipitation = current.get("precipitation")
    if temperature is not None and temperature >= 40:
        risks.append("High heat conditions")
    if wind is not None and wind >= 45:
        risks.append("Strong winds")
    if precipitation is not None and precipitation >= 10:
        risks.append("Heavy precipitation")
    return ("elevated" if risks else "normal", risks or ["No local weather trigger detected from currently connected feeds."])


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/world-state")
async def world_state() -> dict[str, Any]:
    return await get_world_state()


@app.get("/api/brief")
async def incident_brief(city: str = "Hyderabad") -> dict[str, Any]:
    world, weather, air, traffic = await asyncio.gather(get_world_state(), get_weather(city), get_air_quality(city), get_traffic(city))
    risk, factors = risk_label(weather, world["earthquakes"])
    return {
        "title": f"K AI Incident Brief — {weather['city']}",
        "generated_at": datetime.now(UTC).isoformat(),
        "risk_level": risk,
        "weather": weather,
        "air_quality": air,
        "traffic": traffic,
        "marine": {"status": "configured" if os.getenv("AISSTREAM_API_KEY") else "not_configured", "source": "AISStream", "note": "Marine streaming activates through the server-side bridge in the next runtime update."},
        "factors": factors,
        "global_watchlist": [q for q in world["earthquakes"] if (q.get("magnitude") or 0) >= 5],
        "recommended_actions": [
            "Check official local warnings before making operational decisions.",
            "Review the source timestamps and refresh this brief if conditions change.",
            "Escalate to the designated human incident lead when a verified official alert is active.",
        ],
        "sources": world["sources"],
        "disclaimer": world["disclaimer"],
    }
