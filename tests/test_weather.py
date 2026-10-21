from weather_mcp.server import best_window, clock


def hours(start=0, count=24):
    return [f"2026-10-22T{hour:02d}:00" for hour in range(start, start + count)]


def test_clock_strips_the_date():
    assert clock("2026-10-22T06:10") == "06:10"
    assert clock(None) is None


def test_best_window_prefers_a_dry_mild_break():
    times = hours()
    temperatures = [28.0] * 24
    rain = [80.0] * 24
    uv = [5.0] * 24

    for index in range(7, 10):
        rain[index] = 0.0

    result = best_window(times, temperatures, rain, uv)
    assert result is not None
    assert result["start"] == "07:00"
    assert result["end"] == "10:00"
    assert result["max_rain_probability"] == 0


def test_best_window_needs_data():
    assert best_window([], [], [], []) is None
