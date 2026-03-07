# app/schemas/rules.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum

class Operator(str, Enum):
    LT = "<"
    LE = "<="
    EQ = "="
    GT = ">"
    GE = ">="

class ActuatorAction(str, Enum):
    ON = "ON"
    OFF = "OFF"

class RuleCreate(BaseModel):
    sensor: str
    metric: str
    subsystem: Optional[str] = None
    operator: Operator
    value: float
    actuator: str
    action: ActuatorAction
    is_active: bool = True

class RuleResponse(RuleCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)