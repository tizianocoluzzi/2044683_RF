from typing import List

from fastapi import FastAPI

from .config import settings
from .models import Rule, UnifiedSensorEvent
from .rules_engine import RuleEngine

app = FastAPI(title=settings.service_name)

rule_engine = RuleEngine()

#TEMP for testing#
from fastapi import HTTPException
from .actuators_client import ActuatorsClient

@app.get("/test-actuator/{actuator_name}/{state}")
async def test_actuator(actuator_name: str, state: str):
    if state not in ("ON", "OFF"):
        raise HTTPException(status_code=400, detail="state must be ON or OFF")

    client = ActuatorsClient()
    await client.set_state(actuator_name, state)
    return {"actuator": actuator_name, "state": state, "status": "ok"}

#TEMP for testing#

@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


# --------------------
# Rules API
# --------------------


@app.get("/rules", response_model=List[Rule])
async def list_rules():
    return rule_engine.list_rules()


@app.post("/rules", response_model=Rule, status_code=201)
async def create_rule(rule: Rule):
    created = rule_engine.add_rule(rule)
    return created


# -------------------------------
# Sensor API
# -------------------------------


@app.post("/sensor-events")
async def handle_sensor_event(event: UnifiedSensorEvent):
    triggered = await rule_engine.process_event(event)
    return {
        "sensor_id": event.sensor_id,
        "captured_at": event.captured_at,
        "triggered_rules": triggered,
    }
