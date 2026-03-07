from pydantic import BaseModel
from commonTelemetry import Measurement, SubsystemMetrics, CommonTelemetry
from typing import List, Optional, Union

class RestScalar(BaseModel):
    sensor_id: str
    captured_at: str
    metric: str
    value: float
    unit: str
    status: str

    def to_common(self) -> CommonTelemetry:
        return CommonTelemetry(
            sensor_id=self.sensor_id,
            captured_at=self.captured_at,
            status=self.status,
            metrics=[
                SubsystemMetrics(
                    subsystem=self.sensor_id,
                    measurements=[
                        Measurement(
                            metric=self.metric,
                            value=self.value,
                            unit=self.unit
                        )
                    ]
                )
            ]
        )

class ChemistryMeasurement(BaseModel):
    metric: str
    value: float
    unit: str


class RestChemistry(BaseModel):
    sensor_id: str
    captured_at: str
    measurements: List[ChemistryMeasurement]
    status: str

    def to_common(self):

        measurements = [
            Measurement(
                metric=m.metric,
                value=m.value,
                unit=m.unit
            )
            for m in self.measurements
        ]

        return CommonTelemetry(
            sensor_id=self.sensor_id,
            captured_at=self.captured_at,
            status=self.status,
            metrics=[
                SubsystemMetrics(
                    subsystem=self.sensor_id,
                    measurements=measurements
                )
            ]
        )


class RestParticulate(BaseModel):
    sensor_id: str
    captured_at: str
    pm1_ug_m3: float
    pm25_ug_m3: float
    pm10_ug_m3: float
    status: str

    def to_common(self):

        measurements = [
            Measurement(metric="pm1", value=self.pm1_ug_m3, unit="ug/m3"),
            Measurement(metric="pm2.5", value=self.pm25_ug_m3, unit="ug/m3"),
            Measurement(metric="pm10", value=self.pm10_ug_m3, unit="ug/m3"),
        ]

        return CommonTelemetry(
            sensor_id=self.sensor_id,
            captured_at=self.captured_at,
            status=self.status,
            metrics=[
                SubsystemMetrics(
                    subsystem="particulate",
                    measurements=measurements
                )
            ]
        )

class RestLevel(BaseModel):
    sensor_id: str
    captured_at: str
    level_pct: float
    level_liters: float
    status: str

    def to_common(self):

        metrics = [
            SubsystemMetrics(
                subsystem="level_pct",
                measurements=[
                    Measurement(metric="level_pct", value=self.level_pct, unit="%")
                ]
            ),
            SubsystemMetrics(
                subsystem="level_liters",
                measurements=[
                    Measurement(metric="level_liters", value=self.level_liters, unit="L")
                ]
            )
        ]

        return CommonTelemetry(
            sensor_id=self.sensor_id,
            captured_at=self.captured_at,
            status=self.status,
            metrics=metrics
        )


