"""
Kafka Consumer for consuming service metrics
"""

import json
import logging
import os
import asyncio
from typing import Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class MetricsConsumer:
    """Kafka consumer for consuming service metrics and making predictions"""

    def __init__(self, anomaly_detector, prediction_producer):
        """
        Initialize Kafka consumer

        Args:
            anomaly_detector: AnomalyDetector instance
            prediction_producer: PredictionProducer instance
        """
        self.anomaly_detector = anomaly_detector
        self.prediction_producer = prediction_producer
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = os.getenv('KAFKA_TOPIC_METRICS_STREAM', 'metrics-stream')
        self.group_id = os.getenv('KAFKA_CONSUMER_GROUP_ID', 'ml-service-group')

        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True
            )
            logger.info(f"Kafka consumer initialized: {self.bootstrap_servers}, topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages from Kafka"""
        logger.info(f"Starting to consume from topic: {self.topic}")

        try:
            for message in self.consumer:
                try:
                    metrics = message.value
                    logger.debug(f"Received metrics: serviceId={metrics.get('serviceId')}")

                    # Make prediction
                    prediction = await self.anomaly_detector.predict(metrics)

                    # Publish prediction to Kafka
                    if self.prediction_producer:
                        self.prediction_producer.publish_prediction(prediction)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    continue

        except KafkaError as e:
            logger.error(f"Kafka consumer error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}", exc_info=True)
            raise

    def close(self):
        """Close the Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")
