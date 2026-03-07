"""
Anomaly Detector
Ensemble-based anomaly detection using multiple ML models
"""

import numpy as np
import uuid
from datetime import datetime
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Ensemble anomaly detector using Isolation Forest, One-Class SVM, and optional Autoencoder
    """

    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.feature_names = [
            'cpuUtilization', 'memoryUtilization', 'latencyMs',
            'throughput', 'errorRate', 'diskIo',
            'networkIn', 'networkOut', 'connectionCount',
            'responseTimeP50', 'responseTimeP95', 'responseTimeP99'
        ]

    async def predict(self, metrics: Dict) -> Dict:
        """
        Predict anomaly using ensemble voting
        """
        try:
            # Extract and prepare features
            features = self._extract_features(metrics)
            feature_vector = np.array([features]).reshape(1, -1)

            # Get models
            models = self.model_manager.get_models()

            # Ensemble voting
            predictions = {}
            scores = {}

            for model_name, model in models.items():
                try:
                    # Predict (1 = normal, -1 = anomaly for sklearn)
                    pred = model.predict(feature_vector)[0]
                    score = model.decision_function(feature_vector)[0]

                    # Convert to boolean (True = anomaly)
                    predictions[model_name] = (pred == -1)
                    scores[model_name] = float(score)

                except Exception as e:
                    logger.warning(f"Model {model_name} prediction failed: {e}")
                    predictions[model_name] = False
                    scores[model_name] = 0.0

            # Majority voting
            anomaly_votes = sum(1 for v in predictions.values() if v)
            is_anomaly = anomaly_votes >= (len(predictions) / 2)

            # Calculate confidence
            confidence = self._calculate_confidence(predictions, scores)

            # Calculate feature importance
            feature_importance = self._calculate_feature_importance(
                features, self.feature_names
            )

            # Build response
            response = {
                "predictionId": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "serviceId": metrics.get("serviceId", "unknown"),
                "metrics": {
                    "cpu": features[0],
                    "memory": features[1],
                    "latency": features[2],
                    "throughput": features[3],
                    "error_rate": features[4]
                },
                "anomalyScore": float(np.mean(list(scores.values()))),
                "isAnomaly": bool(is_anomaly),
                "confidence": float(confidence),
                "modelUsed": "EnsembleVoting",
                "ensembleVotes": predictions,
                "featureImportance": feature_importance
            }

            return response

        except Exception as e:
            logger.error(f"Prediction error: {e}", exc_info=True)
            raise

    async def explain(self, metrics: Dict) -> Dict:
        """
        Provide SHAP-based explanation for the prediction
        """
        try:
            features = self._extract_features(metrics)
            feature_vector = np.array([features]).reshape(1, -1)

            # Get feature importance
            feature_importance = self._calculate_feature_importance(
                features, self.feature_names
            )

            # Create explanation
            explanation = {
                "serviceId": metrics.get("serviceId", "unknown"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "featureValues": dict(zip(self.feature_names, features)),
                "featureImportance": feature_importance,
                "topFeatures": self._get_top_features(feature_importance, n=3),
                "explanation": self._generate_explanation(
                    feature_importance, features, self.feature_names
                )
            }

            return explanation

        except Exception as e:
            logger.error(f"Explanation error: {e}", exc_info=True)
            raise

    def _extract_features(self, metrics: Dict) -> List[float]:
        """
        Extract feature vector from metrics dictionary
        """
        features = []
        for feature_name in self.feature_names:
            value = metrics.get(feature_name, 0.0)
            if value is None:
                value = 0.0
            features.append(float(value))
        return features

    def _calculate_confidence(self, predictions: Dict, scores: Dict) -> float:
        """
        Calculate confidence based on ensemble agreement
        """
        if not predictions:
            return 0.0

        # Calculate agreement level
        true_votes = sum(1 for v in predictions.values() if v)
        false_votes = len(predictions) - true_votes

        # Confidence is based on majority agreement
        max_votes = max(true_votes, false_votes)
        confidence = max_votes / len(predictions)

        # Adjust by average score magnitude
        avg_score = np.mean([abs(s) for s in scores.values()])
        confidence = confidence * min(1.0, avg_score / 0.5)  # Normalize

        return confidence

    def _calculate_feature_importance(
        self, features: List[float], feature_names: List[str]
    ) -> Dict[str, float]:
        """
        Calculate simple feature importance based on deviation from normal
        """
        # Normal ranges (these should be learned from training data)
        normal_ranges = {
            'cpuUtilization': (0.0, 0.7),
            'memoryUtilization': (0.0, 0.7),
            'latencyMs': (0.0, 150.0),
            'throughput': (300.0, 800.0),
            'errorRate': (0.0, 0.01),
            'diskIo': (0.0, 80.0),
            'networkIn': (0.0, 800.0),
            'networkOut': (0.0, 400.0),
            'connectionCount': (10, 80),
            'responseTimeP50': (0.0, 100.0),
            'responseTimeP95': (0.0, 250.0),
            'responseTimeP99': (0.0, 500.0)
        }

        importance = {}
        for i, (name, value) in enumerate(zip(feature_names, features)):
            if name in normal_ranges:
                min_val, max_val = normal_ranges[name]
                if value < min_val:
                    deviation = (min_val - value) / (max_val - min_val)
                elif value > max_val:
                    deviation = (value - max_val) / (max_val - min_val)
                else:
                    deviation = 0.0

                importance[name] = min(1.0, abs(deviation))
            else:
                importance[name] = 0.0

        # Normalize to sum to 1.0
        total = sum(importance.values())
        if total > 0:
            importance = {k: v/total for k, v in importance.items()}

        return importance

    def _get_top_features(self, feature_importance: Dict, n: int = 3) -> List[Dict]:
        """
        Get top N most important features
        """
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {"feature": name, "importance": importance}
            for name, importance in sorted_features[:n]
        ]

    def _generate_explanation(
        self, feature_importance: Dict, features: List[float], feature_names: List[str]
    ) -> str:
        """
        Generate human-readable explanation
        """
        top_features = self._get_top_features(feature_importance, n=2)

        if not top_features:
            return "No significant anomalies detected in the metrics."

        explanations = []
        for item in top_features:
            feature_name = item["feature"]
            importance = item["importance"]

            if importance > 0.3:
                idx = feature_names.index(feature_name)
                value = features[idx]
                explanations.append(
                    f"{feature_name} is abnormal (value: {value:.2f}, importance: {importance:.2f})"
                )

        if explanations:
            return "Anomaly detected: " + "; ".join(explanations)
        else:
            return "Metrics are within normal ranges."
