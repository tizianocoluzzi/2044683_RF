from pydantic import BaseModel
from typing import List
from commonTelemetry import Measurement, SubsystemMetrics, CommonTelemetry


class TopicPower(BaseModel):
    topic: str
    event_time: str
    subsystem: str
    power_kw: float
    voltage_v: float
    current_a: float
    cumulative_kwh: float

    def to_common(self):

        measurements = [
            Measurement(metric="power_kw", value=self.power_kw, unit="kW"),
            Measurement(metric="voltage_v", value=self.voltage_v, unit="V"),
            Measurement(metric="current_a", value=self.current_a, unit="A"),
            Measurement(metric="cumulative_kwh", value=self.cumulative_kwh, unit="kWh"),
        ]

        return CommonTelemetry(
            sensor_id=self.topic.removeprefix("mars/telemetry/"),
            captured_at=self.event_time,
            metrics=[
                SubsystemMetrics(subsystem=self.subsystem, measurements=measurements)
            ]
        )

class EnvironmentSource(BaseModel):
    system: str
    segment: str


class EnvironmentMeasurement(BaseModel):
    metric: str
    value: float
    unit: str


class TopicEnvironment(BaseModel):
    topic: str
    event_time: str
    source: EnvironmentSource
    measurements: List[EnvironmentMeasurement]
    status: str

    def to_common(self):

        subsystem = f"{self.source.system}.{self.source.segment}"

        measurements = [
            Measurement(
                metric=m.metric,
                value=m.value,
                unit=m.unit
            )
            for m in self.measurements
        ]

        return CommonTelemetry(
            sensor_id=self.topic.removeprefix("mars/telemetry/"),
            captured_at=self.event_time,
            status=self.status,
            metrics=[
                SubsystemMetrics(subsystem=subsystem, measurements=measurements)
            ]
        )

class TopicThermalLoop(BaseModel):
    topic: str
    event_time: str
    loop: str
    temperature_c: float
    flow_l_min: float
    status: str

    def to_common(self):

        measurements = [
            Measurement(metric="temperature", value=self.temperature_c, unit="C"),
            Measurement(metric="flow", value=self.flow_l_min, unit="L/min"),
        ]

        return CommonTelemetry(
            sensor_id=self.topic.removeprefix("mars/telemetry/"),
            captured_at=self.event_time,
            status=self.status,
            metrics=[
                SubsystemMetrics(subsystem=self.loop, measurements=measurements)
            ]
        )


class TopicAirlock(BaseModel):
    topic: str
    event_time: str
    airlock_id: str
    cycles_per_hour: float
    last_state: str

    def to_common(self):

        measurements = [
            Measurement(metric="cycles_per_hour", value=self.cycles_per_hour, unit="cycles/h"),
            Measurement(metric="state", value=self.last_state)
        ]

        return CommonTelemetry(
            sensor_id=self.topic.removeprefix("mars/telemetry/"),
            captured_at=self.event_time,
            metrics=[
                SubsystemMetrics(subsystem=self.airlock_id, measurements=measurements)
            ]
        )

