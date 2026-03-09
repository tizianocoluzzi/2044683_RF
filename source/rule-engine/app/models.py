from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel


# ---------------------------
# Rule engine models
# ---------------------------


class Operator(str, Enum):
    gt = ">"
    lt = "<"
    eq = "="


class ActuatorAction(str, Enum):
    ON = "ON"
    OFF = "OFF"


class Rule(BaseModel):
    id: int
    sensor: str                  # es. "greenhousetemperature"
    metric: str                  # es. "temperature_c"
    subsystem: Optional[str] = None  # opzionale per filtrare sul subsystem
    operator: Operator
    value: float
    actuator: str                # es. "cooling_fan"
    action: ActuatorAction       # "ON" / "OFF"
    is_active: bool = True


# -----------------------------------
# Sensor models
# -----------------------------------


class MeasurementStatus(str, Enum):
    ok = "ok"
    warning = "warning"


class Measurement(BaseModel):
    metric: str
    value: Union[str, float]      
    unit: Optional[str] = None
    status: Optional[MeasurementStatus] = None


class MetricGroup(BaseModel):
    subsystem: str
    measurements: List[Measurement]


class SensorStatus(str, Enum):
    ok = "ok"
    warning = "warning"


class UnifiedSensorEvent(BaseModel):
    sensor_id: str
    captured_at: str
    status: Optional[SensorStatus] = None
    metrics: List[MetricGroup]

# -----------------------------------
# Actuator models
# -----------------------------------

class ActuatorMode(str, Enum):
    AUTO = "AUTO"
    ON = "ON"
    OFF = "OFF"


class ActuatorOverrideRequest(BaseModel):
    actuator: str
    mode: ActuatorMode
