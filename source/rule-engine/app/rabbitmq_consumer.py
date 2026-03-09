import asyncio
import logging

import pika

from .config import settings
from .models import UnifiedSensorEvent
from .rules_engine import RuleEngine

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.connection = None
        self.channel = None

    def connect(self):
        """Connect to RabbitMQ."""
        credentials = pika.PlainCredentials("guest", "guest")
        parameters = pika.ConnectionParameters(
            host="rabbitmq",
            port=5672,
            credentials=credentials,
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        logger.info("Connected to RabbitMQ")

    def start(self):
        """
        Start consuming sensor messages.
        This method is intended to run inside one dedicated background thread.
        """
        self.connect()

        self.channel.queue_declare(queue="sensors", durable=True)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue="sensors",
            on_message_callback=self.on_sensor_message,
        )

        logger.info("Starting RabbitMQ consumer on queue: sensors")
        self.channel.start_consuming()

    def on_sensor_message(self, ch, method, properties, body):
        """Handle sensor message."""
        try:
            logger.info("Sensor message received: %s", body[:100])

            event = UnifiedSensorEvent.model_validate_json(body)
            triggered = asyncio.run(self.rule_engine.process_event(event))

            logger.info(
                "Processed sensor %s, triggered: %s",
                event.sensor_id,
                len(triggered),
            )

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error("Sensor error: %s", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def stop(self):
        """Stop consumer."""
        try:
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
        except Exception as e:
            logger.error("Error while stopping consuming: %s", e)

        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            logger.error("Error while closing RabbitMQ connection: %s", e)

        logger.info("RabbitMQ consumer stopped")
