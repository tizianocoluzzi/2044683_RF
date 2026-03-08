import logging
from typing import List
from threading import Thread

from fastapi import FastAPI

from .config import settings
from .rabbitmq_consumer import RabbitMQConsumer
from .models import Rule, UnifiedSensorEvent
from .rules_engine import RuleEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.service_name)

rule_engine = RuleEngine()

rabbit_consumer: RabbitMQConsumer | None = None

@app.on_event("startup")
def startup() -> None:
    """
    Start the RabbitMQ consumer in a background thread.
    This avoids blocking the FastAPI main thread.
    """
    global rabbit_consumer

    if rabbit_consumer is None:
        rabbit_consumer = RabbitMQConsumer(rule_engine)

    Thread(target=rabbit_consumer.start, daemon=True).start()
    logger.info("%s started", settings.service_name)


@app.on_event("shutdown")
def shutdown() -> None:
    """
    Stop the RabbitMQ consumer gracefully on shutdown.
    """
    global rabbit_consumer

    if rabbit_consumer is not None:
        try:
            rabbit_consumer.stop()
        except Exception as exc:
            logger.error("Error while stopping RabbitMQ consumer: %s", exc)


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