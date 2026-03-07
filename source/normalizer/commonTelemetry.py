import json
from pydantic import BaseModel
from typing import List, Optional, Union
class Measurement(BaseModel):
    metric: str
    value: Union[float, str]
    unit: Optional[str] = None


class SubsystemMetrics(BaseModel):
    subsystem: str
    measurements: List[Measurement]


class CommonTelemetry(BaseModel):
    sensor_id: str
    captured_at: str
    metrics: List[SubsystemMetrics]
    status: Optional[str] = None

