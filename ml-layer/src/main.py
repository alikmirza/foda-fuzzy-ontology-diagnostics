"""
FODA ML Anomaly Detection Service
FastAPI application for ML-based anomaly detection
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
from datetime import datetime

from ml.anomaly_detector import AnomalyDetector
from ml.model_manager import ModelManager
from kafka.kafka_consumer import MetricsConsumer
from kafka.kafka_producer import PredictionProducer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FODA ML Anomaly Detection Service",
    description="Machine Learning service for detecting anomalies in microservice metrics",
    version="1.0.0"
)

# Global instances
model_manager: Optional[ModelManager] = None
anomaly_detector: Optional[AnomalyDetector] = None
metrics_consumer: Optional[MetricsConsumer] = None
prediction_producer: Optional[PredictionProducer] = None


class ServiceMetrics(BaseModel):
    """Service metrics model"""
    serviceId: str
    timestamp: str
    cpuUtilization: float
    memoryUtilization: float
    latencyMs: float
    throughput: float
    errorRate: float
    diskIo: Optional[float] = None
    networkIn: Optional[float] = None
    networkOut: Optional[float] = None
    connectionCount: Optional[int] = None
    requestCount: Optional[int] = None
    responseTimeP50: Optional[float] = None
    responseTimeP95: Optional[float] = None
    responseTimeP99: Optional[float] = None


class PredictionRequest(BaseModel):
    """Prediction request model"""
    metrics: ServiceMetrics


class PredictionResponse(BaseModel):
    """Prediction response model"""
    predictionId: str
    timestamp: str
    serviceId: str
    metrics: Dict
    anomalyScore: float
    isAnomaly: bool
    confidence: float
    modelUsed: str
    ensembleVotes: Dict[str, bool]
    featureImportance: Dict[str, float]


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global model_manager, anomaly_detector, metrics_consumer, prediction_producer

    logger.info("Starting FODA ML Anomaly Detection Service...")

    try:
        # Initialize model manager
        model_manager = ModelManager()
        logger.info("Model manager initialized")

        # Initialize anomaly detector
        anomaly_detector = AnomalyDetector(model_manager)
        logger.info("Anomaly detector initialized")

        # Initialize Kafka producer
        try:
            prediction_producer = PredictionProducer()
            logger.info("Kafka producer initialized")
        except Exception as e:
            logger.warning(f"Kafka producer initialization failed: {e}. Continuing without Kafka support.")
            prediction_producer = None

        # Initialize Kafka consumer (optional, can be started separately)
        # Uncomment to enable automatic metrics consumption from Kafka
        # if prediction_producer:
        #     metrics_consumer = MetricsConsumer(anomaly_detector, prediction_producer)
        #     asyncio.create_task(metrics_consumer.start_consuming())

        logger.info("Service started successfully!")
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        raise


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "FODA ML Anomaly Detection Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/predict", response_model=PredictionResponse)
async def predict_anomaly(request: PredictionRequest):
    """
    Predict if the given metrics indicate an anomaly
    """
    if anomaly_detector is None:
        raise HTTPException(status_code=503, detail="Anomaly detector not initialized")

    try:
        # Convert metrics to dict
        metrics_dict = request.metrics.dict()

        # Make prediction
        prediction = await anomaly_detector.predict(metrics_dict)

        # Publish to Kafka if producer is available and it's an anomaly
        if prediction_producer and prediction.get('isAnomaly'):
            try:
                prediction_producer.publish_prediction(prediction)
                logger.info(f"Published prediction to Kafka: {prediction.get('predictionId')}")
            except Exception as kafka_error:
                logger.error(f"Failed to publish to Kafka: {kafka_error}")
                # Continue even if Kafka publish fails

        return JSONResponse(content=prediction)

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/explain")
async def explain_prediction(request: PredictionRequest):
    """
    Explain the prediction using SHAP values
    """
    if anomaly_detector is None:
        raise HTTPException(status_code=503, detail="Anomaly detector not initialized")

    try:
        metrics_dict = request.metrics.dict()
        explanation = await anomaly_detector.explain(metrics_dict)
        return JSONResponse(content=explanation)

    except Exception as e:
        logger.error(f"Explanation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")


@app.post("/train")
async def train_models(training_data: Optional[Dict] = None):
    """
    Train or retrain ML models
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        result = await model_manager.train_models(training_data)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@app.get("/model-info")
async def get_model_info():
    """
    Get information about current models
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        info = model_manager.get_model_info()
        return JSONResponse(content=info)

    except Exception as e:
        logger.error(f"Failed to get model info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
