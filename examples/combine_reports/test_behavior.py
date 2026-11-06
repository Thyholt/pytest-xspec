"""Illustrative pump checks using simulated benches, without medical hardware."""

import pytest


class SimulatedVolumeBench:
    def measure_delivered_volume(self, rate_ml_per_hour: float, duration_minutes: float) -> float:
        return rate_ml_per_hour * duration_minutes / 60 * 0.99


class SimulatedAlarmBench:
    def measure_downstream_occlusion_alarm_delay(self) -> float | None:
        """Simulate an audible alarm 12 seconds after blocking the line at 60 mL/h."""
        return 12.0


@pytest.mark.xspec("REQ-001")
def test_delivery_volume() -> None:
    bench = SimulatedVolumeBench()

    delivered_volume_ml = bench.measure_delivered_volume(rate_ml_per_hour=60, duration_minutes=10)

    assert 9.5 <= delivered_volume_ml <= 10.5


@pytest.mark.xspec("REQ-001")
def test_occlusion_alarm() -> None:
    bench = SimulatedAlarmBench()

    alarm_delay_s = bench.measure_downstream_occlusion_alarm_delay()

    assert alarm_delay_s is not None
    assert 0 <= alarm_delay_s <= 30
