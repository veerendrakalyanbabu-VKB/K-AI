from app.main import risk_label


def test_risk_label_marks_high_heat() -> None:
    weather = {"current": {"temperature_2m": 42, "wind_speed_10m": 10, "precipitation": 0}}
    level, factors = risk_label(weather, [])
    assert level == "elevated"
    assert "High heat conditions" in factors


def test_risk_label_is_normal_without_trigger() -> None:
    weather = {"current": {"temperature_2m": 24, "wind_speed_10m": 10, "precipitation": 0}}
    level, factors = risk_label(weather, [])
    assert level == "normal"
    assert len(factors) == 1
