import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pika
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── configuration ────────────────────────────────────────────────────
RABBITMQ_HOST     = os.getenv("RABBITMQ_HOST",     "localhost")
RABBITMQ_PORT     = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER     = os.getenv("RABBITMQ_USER",     "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

SENSOR_QUEUE      = "sensors"
ACTUATOR_QUEUE    = "actuators"
RULES_SERVICE_URL = os.getenv("RULES_SERVICE_URL", "http://localhost:8001")
RULE_ENGINE_URL   = os.getenv("RULE_ENGINE_URL",   "http://localhost:8000")

# ── shared state ─────────────────────────────────────────────────────
_lock            = threading.Lock()
latest_sensors:   dict[str, dict] = {}
latest_actuators: dict[str, dict] = {}


# ── RabbitMQ callbacks ───────────────────────────────────────────────

def _on_sensor(ch, method, properties, body):
    try:
        msg = json.loads(body)
        sensor_id = msg.get("sensor_id", "unknown").removeprefix("mars/telemetry/")
        msg["sensor_id"] = sensor_id
        with _lock:
            latest_sensors[sensor_id] = msg
    except Exception as e:
        print(f"[sensor consumer] parse error: {e}")


def _on_actuator(ch, method, properties, body):
    try:
        msg = json.loads(body)
        actuator_id = msg.get("actuator_id", "unknown")
        with _lock:
            latest_actuators[actuator_id] = msg
    except Exception as e:
        print(f"[actuator consumer] parse error: {e}")


# ── RabbitMQ consumer thread ─────────────────────────────────────────

def _consume(queue: str, callback):
    """Connect to RabbitMQ and consume *queue*, reconnecting on failure."""
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
            )
            conn = pika.BlockingConnection(params)
            ch   = conn.channel()
            ch.queue_declare(queue=queue, durable=True)
            ch.basic_consume(queue=queue, on_message_callback=callback, auto_ack=True)
            print(f"[{queue}] consumer ready")
            ch.start_consuming()
        except Exception as e:
            print(f"[{queue}] consumer error: {e}. Retrying in 5s…")
            time.sleep(5)


def _start_consumers():
    for queue, cb in [(SENSOR_QUEUE, _on_sensor), (ACTUATOR_QUEUE, _on_actuator)]:
        t = threading.Thread(target=_consume, args=(queue, cb), daemon=True)
        t.start()


# ── FastAPI app ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_consumers()
    yield

app = FastAPI(
    title="Mars Base Telemetry Dashboard",
    description="Displays live sensor and actuator data from the normalizer service.",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/image", StaticFiles(directory=str(Path(__file__).parent / "image")), name="image")


# ── routes ────────────────────────────────────────────────────────────

@app.get("/", summary="Telemetry dashboard", response_description="HTML dashboard page")
async def index(request: Request):
    """Render the live telemetry dashboard."""
    with _lock:
        sensors   = dict(sorted(latest_sensors.items()))
        actuators = dict(sorted(latest_actuators.items()))
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "sensors": sensors, "actuators": actuators},
    )


@app.get("/api/sensors", summary="Latest sensor data (JSON)")
async def api_sensors():
    """Return the latest normalized reading for every sensor."""
    with _lock:
        return dict(sorted(latest_sensors.items()))


@app.get("/api/actuators", summary="Latest actuator states (JSON)")
async def api_actuators():
    """Return the latest state for every actuator."""
    with _lock:
        return dict(sorted(latest_actuators.items()))

@app.post("/api/actuators/{actuator_id}/manual", summary="Manual actuator override")
async def manual_actuator_override(actuator_id: str, request: Request):
    """Fan-out a manual actuator command to the rule-engine (set mode) and
    disable any related rules in the rules-service."""
    body = await request.json()
    mode = body.get("state", "OFF")  # "ON" | "OFF" | "AUTO"

    errors: list[str] = []
    results: dict = {}
    async with httpx.AsyncClient() as client:
        # POST /actuator-control on the rule-engine to override the actuator mode
        try:
            re_resp = await client.post(
                f"{RULE_ENGINE_URL}/actuator-control",
                json={"actuator": actuator_id, "mode": mode},
                timeout=10.0,
            )
            results["rule_engine"] = re_resp.json() if re_resp.content else {}
        except httpx.RequestError as e:
            errors.append(f"rule-engine unreachable: {e}")

        # PATCH /api/rules/actuator/{actuator_id}/disable on the rules-service
        # to deactivate all rules that target this actuator
        try:
            rs_resp = await client.patch(
                f"{RULES_SERVICE_URL}/api/rules/actuator/{actuator_id}/disable",
                timeout=10.0,
            )
            results["rules_service"] = rs_resp.json() if rs_resp.content else {}
        except httpx.RequestError as e:
            errors.append(f"rules-service unreachable: {e}")

    if errors and not results:
        raise HTTPException(status_code=502, detail="; ".join(errors))
    return {"results": results, "errors": errors}



@app.post("/api/rules", summary="Create a rule (proxied to rules_service)")
async def proxy_create_rule(request: Request):
    """Forward a rule payload to the rules_service POST /api/rules/."""
    body = await request.json()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{RULES_SERVICE_URL}/api/rules/",
                json=body,
                timeout=10.0,
            )
            body = await request.json()
            print("Forwarding to rules_service:", body)  # add this
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Rules service unreachable: {e}")


@app.put("/api/rules/{rule_id}", summary="Update a rule (proxied to rules_service)")
async def proxy_update_rule(rule_id: int, request: Request):
    """Forward an update payload to the rules_service PUT /api/rules/{rule_id}."""
    body = await request.json()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.put(
                f"{RULES_SERVICE_URL}/api/rules/{rule_id}",
                json=body,
                timeout=10.0,
            )
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Rules service unreachable: {e}")


@app.delete("/api/rules/{rule_id}", summary="Delete a rule (proxied to rules_service)")
async def proxy_delete_rule(rule_id: int):
    """Forward a delete request to the rules_service DELETE /api/rules/{rule_id}."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.delete(
                f"{RULES_SERVICE_URL}/api/rules/{rule_id}",
                timeout=10.0,
            )
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Rules service unreachable: {e}")
