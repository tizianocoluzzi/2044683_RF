import json
import logging
import pika
import threading
from typing import List
import asyncio

from .config import settings
from .models import Rule, UnifiedSensorEvent
from .rules_engine import RuleEngine

logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.connection = None
        self.channel = None
        self.thread = None

    def connect(self):
        """Connect to RabbitMQ."""
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(host='rabbitmq', port=5672, credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        logger.info("Connected to RabbitMQ")

    def start(self):
        """Start consumer in background thread."""
        self.connect()
        
        # Declare queues
        self.channel.queue_declare(queue='rules-queue', durable=True)
        self.channel.queue_declare(queue='sensors', durable=True)
        
        # Callback
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue='sensors', on_message_callback=self.on_sensor_message)
        self.channel.basic_consume(queue='rules-queue', on_message_callback=self.on_rule_message)
        
        logger.info("Starting RabbitMQ consumer...")
        self.thread = threading.Thread(target=self.channel.start_consuming)
        self.thread.daemon = True
        self.thread.start()

    def on_sensor_message(self, ch, method, properties, body):
        """Handle sensor message."""
        try:
            logger.info(f"Sensor message received: {body[:100]}...")
            event = UnifiedSensorEvent.model_validate_json(body)
            triggered = asyncio.run(self.rule_engine.process_event(event))  # Run async in sync
            logger.info(f"Processed sensor {event.sensor_id}, triggered: {len(triggered)}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Sensor error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def on_rule_message(self, ch, method, properties, body):
        """Handle rule message."""
        try:
            logger.info(f"Rule message received")
            rule = Rule.model_validate_json(body)
            self.rule_engine.add_rule(rule)
            logger.info(f"✅ Rule added: {rule.sensor}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Rule error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def stop(self):
        """Stop consumer."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("RabbitMQ consumer stopped")
