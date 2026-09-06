import asyncio
import time

import httpx
from fastapi.testclient import TestClient

from app import feeds
from app.main import app, risk_label


def test_missing_weather_is_unknown():
    assert risk_label({"current": {}}, [{"magnitude": 8}])[0] == "unknown"


def test_global_quake_does_not_change_local_weather():
    assert risk_label({"current": {"temperature_2m": 25, "wind_speed_10m": 4, "precipitation": 0}}, [{"magnitude": 8}])[0] == "normal"


def test_invalid_positions():
    assert not feeds.position(91, 10)
    assert not feeds.position(float("nan"), 10)
    assert not feeds.position(None, 10)
    assert feeds.position(0, 0)


def test_marine_normalizes_and_expires(monkeypatch):
    feeds.vessels.clear()
    feeds.ingest_vessel({"MessageType": "PositionReport", "MetaData": {"MMSI": 123456789, "Latitude": 15, "Longitude": 70, "ShipName": " Test "}, "Message": {"PositionReport": {"Valid": True, "Sog": 3}}})
    response = asyncio.run(feeds.layer_data("marine"))
    assert response["items"][0]["title"] == "Test"
    assert "received" not in response["items"][0]
    feeds.vessels["123456789"]["received"] = time.monotonic() - 601
    assert asyncio.run(feeds.layer_data("marine"))["items"] == []


def test_key_not_configured_and_unknown_layer(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/api/layers/traffic").json()["status"] == "not_configured"
    assert client.get("/api/layers/unknown").status_code == 404
    assert client.get("/api/layers/weather?city=Unknown").status_code == 400


def test_cache_and_failure_redaction(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, *args, **kwargs):
            calls.append(1)
            raise httpx.RequestError("secret-key-must-not-leak")
    monkeypatch.setattr(feeds.httpx, "AsyncClient", Client)
    async def exercise():
        a = await feeds.cached("test-failure", "https://example.org", 300)
        b = await feeds.cached("test-failure", "https://example.org", 300)
        return a, b
    a, b = asyncio.run(exercise())
    assert a == b and len(calls) == 1
    assert a["status"] == "unavailable"
    assert "secret" not in str(a)


def test_weather_and_traffic_envelopes(monkeypatch):
    async def fake(name, url, ttl, params=None, raw=False):
        return {"status": "available", "fetched_at": "2026-09-06T00:00:00Z", "data": {"current": {"time": "2026-09-06T00:00", "temperature_2m": 25}, "flowSegmentData": {"currentSpeed": 12, "freeFlowSpeed": 30}}}
    monkeypatch.setattr(feeds, "cached", fake)
    monkeypatch.setenv("TOMTOM_API_KEY", "private-test-value")
    weather = asyncio.run(feeds.layer_data("weather"))
    traffic = asyncio.run(feeds.layer_data("traffic"))
    assert weather["items"][0]["metrics"]["temperature_2m"] == 25
    assert traffic["items"][0]["metrics"]["currentSpeed"] == 12
    assert "private-test-value" not in str(traffic)


def test_dashboard_and_health():
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    page = client.get("/")
    assert page.status_code == 200 and 'id="drawer"' in page.text
    assert client.get("/api/layers/cams").json()["status"] == "links_only"


def test_provider_quota_reason_does_not_leak_key(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, *args, **kwargs):
            return httpx.Response(429, request=httpx.Request("GET", "https://example.org/?key=private-value"))
    monkeypatch.setattr(feeds.httpx, "AsyncClient", Client)
    result = asyncio.run(feeds.cached("test-quota", "https://example.org", 300))
    assert result["status"] == "unavailable"
    assert "quota reached" in result["reason"]
    assert "private-value" not in str(result)
