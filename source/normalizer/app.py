from fastapi import FastAPI, HTTPException
import asyncio
import json
from contextlib import asynccontextmanager
import websockets
from fastapi import WebSocket, WebSocketDisconnect
import httpx
from rabbitMQ import RabbitMQ
from commonTelemetry import Measurement, SubsystemMetrics, CommonTelemetry
from rest import (
    RestScalar,
    RestChemistry,
    RestParticulate,
    RestLevel,
)
from topics import (
    TopicPower,
    TopicEnvironment,
    TopicThermalLoop,
    TopicAirlock,
)


API_BASE_URL = "http://localhost:8080"
WS_BASE_URL = "ws://localhost:8080"

# ── Topic → Model mapping ────────────────────────────────────────────
TOPIC_MODEL_MAP = {
    "mars/telemetry/solar_array":       TopicPower,
    "mars/telemetry/power_bus":         TopicPower,
    "mars/telemetry/power_consumption": TopicPower,
    "mars/telemetry/radiation":         TopicEnvironment,
    "mars/telemetry/life_support":      TopicEnvironment,
    "mars/telemetry/thermal_loop":      TopicThermalLoop,
    "mars/telemetry/airlock":           TopicAirlock,
}

# ── REST sensor → Model mapping ──────────────────────────────────────
REST_MODEL_MAP = {
    "greenhouse_temperature": RestScalar,
    "entrance_humidity":      RestScalar,
    "co2_hall":               RestScalar,
    "corridor_pressure":      RestScalar,
    "hydroponic_ph":          RestChemistry,
    "air_quality_voc":        RestChemistry,
    "air_quality_pm25":       RestParticulate,
    "water_tank_level":       RestLevel,
}

TOPICS = list(TOPIC_MODEL_MAP.keys())
REST_SENSORS = list(REST_MODEL_MAP.keys())

latest_telemetry: dict[str, dict] = {t: {} for t in TOPICS}
latest_sensors: dict[str, dict] = {s: {} for s in REST_SENSORS}

SENSOR_POLL_INTERVAL = 5  # seconds


# ── Normalization helpers ─────────────────────────────────────────────

def normalize_topic(topic_name: str, raw: dict) -> CommonTelemetry:
    """Parse a raw topic message and return the CommonTelemetry form."""
    model_cls = TOPIC_MODEL_MAP.get(topic_name)
    if model_cls is None:
        raise ValueError(f"Unknown topic: {topic_name}")
    return model_cls(**raw).to_common()


def normalize_rest(sensor_name: str, raw: dict) -> CommonTelemetry:
    """Parse a raw REST sensor payload and return the CommonTelemetry form."""
    model_cls = REST_MODEL_MAP.get(sensor_name)
    if model_cls is None:
        raise ValueError(f"Unknown REST sensor: {sensor_name}")
    return model_cls(**raw).to_common()


# ── Background WebSocket listener ────────────────────────────────────

async def telemetry_listener(topic: str):
    """Subscribe to upstream WebSocket, normalize, and store latest data."""
    global latest_telemetry
    while True:
        try:
            async with websockets.connect(
                f"{WS_BASE_URL}/api/telemetry/ws?topic={topic}"
            ) as ws:
                async for message in ws:
                    try:
                        raw = json.loads(message)
                        common = normalize_topic(topic, raw)
                        latest_telemetry[topic] = common.model_dump()
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"[{topic}] normalization error: {e}")
                        latest_telemetry[topic] = {"raw": message}
        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            print(f"WebSocket connection lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)


async def sensor_poller():
    """Background task: poll every REST sensor endpoint every SENSOR_POLL_INTERVAL seconds."""
    async with httpx.AsyncClient() as client:
        while True:
            for sensor in REST_SENSORS:
                try:
                    resp = await client.get(f"{API_BASE_URL}/api/sensors/{sensor}")
                    resp.raise_for_status()
                    raw = resp.json()
                    common = normalize_rest(sensor, raw)
                    latest_sensors[sensor] = common.model_dump()
                except Exception as e:
                    print(f"[{sensor}] poll error: {e}")
            await asyncio.sleep(SENSOR_POLL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    for t in TOPICS:
        tasks.append(asyncio.create_task(telemetry_listener(t)))
    tasks.append(asyncio.create_task(sensor_poller()))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Normalizer", lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/test_rabbit")
async def test():

    rabbitmq = RabbitMQ()
    message = 'Test message'
    queue_name = 'queue'
    rabbitmq.publish(queue_name, message)
    print(f"Sent message: {message}")
    rabbitmq.close()
    return {'status':'ok'}


@app.get("/sensors")
async def get_all_sensors():
    """Return the latest cached sensor data (polled every 5s)."""
    if not any(latest_sensors.values()):
        raise HTTPException(status_code=503, detail="No sensor data available yet")
    return latest_sensors


@app.get("/sensors/{sensor_name}")
async def get_cached_sensor(sensor_name: str):
    """Return the latest cached data for a single sensor."""
    if sensor_name not in latest_sensors:
        raise HTTPException(status_code=404, detail=f"Unknown sensor: {sensor_name}")
    if not latest_sensors[sensor_name]:
        raise HTTPException(status_code=503, detail=f"No data yet for {sensor_name}")
    return latest_sensors[sensor_name]


@app.get("/ws")
async def get_telemetry():
    """Return the latest telemetry data as plain JSON."""
    if not latest_telemetry:
        raise HTTPException(status_code=503, detail="No telemetry data available yet")
    return latest_telemetry
