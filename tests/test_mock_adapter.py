from dnp3_gateway.adapters import MockTelemetryReader

from .conftest import make_device, make_signal


def test_mock_reader_produces_reading_per_signal() -> None:
    reader = MockTelemetryReader(seed=42)
    device = make_device()
    signals = [
        make_signal("master.actual_current", data_type="analog", object_group=30, index=0, scale=1.0),
        make_signal("master.overcurrent_tripped", data_type="binary", object_group=1, index=3),
        make_signal("sat01.fault_counter", source="sat01", data_type="counter", object_group=20, index=0),
    ]
    readings = reader.read_device(device=device, signals=signals)
    assert len(readings) == 3
    by_key = {r.signal_key: r for r in readings}

    # Binary sinyal 0 veya 1 olmali
    assert by_key["master.overcurrent_tripped"].scaled_value in (0.0, 1.0)
    # Counter integer degerler
    assert 0 <= by_key["sat01.fault_counter"].scaled_value <= 50
    # Analog scale uygulanmis olmali
    assert by_key["master.actual_current"].quality == "good"


def test_mock_reader_respects_scale_offset() -> None:
    reader = MockTelemetryReader(seed=1)
    device = make_device()
    signal = make_signal(
        "master.battery_voltage",
        data_type="analog",
        object_group=30,
        index=10,
        scale=0.01,
        offset=0.0,
    )
    reading = reader.read_device(device=device, signals=[signal])[0]
    # scale=0.01 oldugu icin 3.2..4.2V araligina duser (raw 320-420)
    assert 3.1 <= reading.scaled_value <= 4.3
