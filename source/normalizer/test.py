import json
import threading
from rabbitMQ import RabbitMQ

# All queues the normalizer publishes to
TOPIC_QUEUES = [
    "mars/telemetry/solar_array",
    "mars/telemetry/power_bus",
    "mars/telemetry/power_consumption",
    "mars/telemetry/radiation",
    "mars/telemetry/life_support",
    "mars/telemetry/thermal_loop",
    "mars/telemetry/airlock",
]

REST_QUEUES = [
    "greenhouse_temperature",
    "entrance_humidity",
    "co2_hall",
    "corridor_pressure",
    "hydroponic_ph",
    "air_quality_voc",
    "air_quality_pm25",
    "water_tank_level",
]

ACTUATOR_QUEUES = [
    "cooling_fan",
    "entrance_humidifier",
    "hall_ventilation",
    "habitat_heater",
]

ALL_QUEUES = TOPIC_QUEUES + REST_QUEUES + ACTUATOR_QUEUES


def on_message(ch, method, properties, body):
    queue = method.routing_key
    try:
        data = json.loads(body)
        print(f"[{queue}] {json.dumps(data, indent=2)}")
    except json.JSONDecodeError:
        print(f"[{queue}] (raw) {body.decode()}")


def consume_queue(queue_name):
    """Each thread gets its own RabbitMQ connection and consumes one queue."""
    rabbit = RabbitMQ()
    rabbit.channel.queue_declare(queue=queue_name, durable=True)
    print(f"Listening on queue: {queue_name}")
    rabbit.consume(queue_name, on_message)


if __name__ == "__main__":
    threads = []
    for q in ALL_QUEUES:
        t = threading.Thread(target=consume_queue, args=(q,), daemon=True)
        t.start()
        threads.append(t)

    print(f"\nConsuming from {len(ALL_QUEUES)} queues. Press Ctrl+C to stop.\n")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nStopped.")
