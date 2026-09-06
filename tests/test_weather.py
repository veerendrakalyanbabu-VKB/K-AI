from app.weather import normalize


def test_forecast_units_validity_and_attribution():
    row = {"time": "2026-09-06T12:00:00Z", "data": {"instant": {"details": {"air_temperature": 28, "wind_speed": 5}}, "next_1_hours": {"details": {"precipitation_amount": 1.2}}}}
    from datetime import datetime
    timestamp = datetime.fromisoformat("2026-09-06T12:20:00+00:00").timestamp()
    result = normalize({"properties": {"timeseries": [row]}}, "Hyderabad", 17, 78, timestamp)
    item = result["items"][0]
    assert item["metrics"]["wind_speed_10m"] == 18
    assert item["metrics"]["precipitation"] == 1.2
    assert "CC BY 4.0" in item["source"]
    assert "next-hour" in result["coverage"]
    assert normalize({"properties": {"timeseries": [row]}}, "Hyderabad", 17, 78, timestamp+7200)["status"] == "unavailable"


def test_missing_rain_is_not_assumed_zero():
    from datetime import datetime
    row = {"time": "2026-09-06T12:00:00Z", "data": {"instant": {"details": {"air_temperature": 28}}}}
    result = normalize({"properties": {"timeseries": [row]}}, "Hyderabad", 17, 78, datetime.fromisoformat("2026-09-06T12:00:00+00:00").timestamp())
    assert result["items"][0]["metrics"]["precipitation"] is None
