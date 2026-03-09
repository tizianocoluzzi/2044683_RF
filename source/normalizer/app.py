import asyncio
import json
import os
import signal
import websockets
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
from actuator import RestActuators, RestActuator


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
WS_BASE_URL  = os.getenv("WS_BASE_URL",  "ws://localhost:8080")

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

ACTUATOR_ENDPOINT = os.getenv("ACTUATOR_ENDPOINT", "/api/actuators")

TOPICS = list(TOPIC_MODEL_MAP.keys())
REST_SENSORS = list(REST_MODEL_MAP.keys())

latest_telemetry: dict[str, dict] = {t: {} for t in TOPICS}
latest_sensors: dict[str, dict] = {s: {} for s in REST_SENSORS}
latest_actuators: dict[str, dict] = {}

SENSOR_POLL_INTERVAL = int(os.getenv("SENSOR_POLL_INTERVAL", "5"))  # seconds

sensor_queue = "sensors"
actuator_queue = "actuators"



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


def normalize_actuators(raw: dict) -> list[RestActuator]:
    """Parse the actuators payload and return one RestActuator per entry.

    Input:  {"actuators": {"cooling_fan": "OFF", ...}}
    Output: [RestActuator(actuator_id="cooling_fan", state="OFF"), ...]
    """
    return RestActuators(**raw).to_list()


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

                        try:
                            rabbitmq = RabbitMQ()
                            rabbitmq.publish(sensor_queue, json.dumps(common.model_dump()))
                            rabbitmq.close()
                        except Exception as e:
                            print(f"RabbitMQ publish error in topic {topic}: {e}")
                    
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
                    
                    try:
                        rabbitmq = RabbitMQ()
                        rabbitmq.publish(sensor_queue, json.dumps(common.model_dump()))
                        rabbitmq.close()
                    except Exception as e:
                        print(f"RabbitMQ publish error in sensor {sensor}: {e}")
                    
                except Exception as e:
                    print(f"[{sensor}] poll error: {e}")
            await asyncio.sleep(SENSOR_POLL_INTERVAL)

async def actuator_poller():
    """Background task: poll the actuators endpoint and publish each actuator separately."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(f"{API_BASE_URL}{ACTUATOR_ENDPOINT}")
                resp.raise_for_status()
                raw = resp.json()
                messages = normalize_actuators(raw)

                for msg in messages:
                    latest_actuators[msg.actuator_id] = msg.model_dump()
                    try:
                        rabbitmq = RabbitMQ()
                        rabbitmq.publish(actuator_queue, json.dumps(msg.model_dump()))
                        rabbitmq.close()
                    except Exception as e:
                        print(f"RabbitMQ publish error for actuator {msg.actuator_id}: {e}")

            except Exception as e:
                print(f"[actuator_poller] poll error: {e}")
            await asyncio.sleep(SENSOR_POLL_INTERVAL)


async def main():
    tasks = []
    for t in TOPICS:
        tasks.append(asyncio.create_task(telemetry_listener(t)))
    tasks.append(asyncio.create_task(sensor_poller()))
    tasks.append(asyncio.create_task(actuator_poller()))

    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    print("Normalizer running. Press Ctrl+C to stop.")
    await stop

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())

