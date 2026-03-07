"""
Kafka Producer for publishing ML predictions
"""

import json
import logging
import os
from typing import Dict
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class PredictionProducer:
    """Kafka producer for publishing anomaly predictions"""

    def __init__(self):
        """Initialize Kafka producer"""
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = os.getenv('KAFKA_TOPIC_ML_PREDICTIONS', 'ml-predictions')

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            logger.info(f"Kafka producer initialized: {self.bootstrap_servers}, topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise

    def publish_prediction(self, prediction: Dict):
        """
        Publish a prediction to Kafka

        Args:
            prediction: Dictionary containing prediction data
        """
        try:
            service_id = prediction.get('serviceId', 'unknown')

            # Send to Kafka
            future = self.producer.send(
                self.topic,
                key=service_id,
                value=prediction
            )

            # Wait for confirmation
            record_metadata = future.get(timeout=10)

            logger.info(
                f"Published prediction: topic={record_metadata.topic}, "
                f"partition={record_metadata.partition}, "
                f"offset={record_metadata.offset}, "
                f"predictionId={prediction.get('predictionId')}"
            )

        except KafkaError as e:
            logger.error(f"Kafka error publishing prediction: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error publishing prediction: {e}", exc_info=True)
            raise

    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")
