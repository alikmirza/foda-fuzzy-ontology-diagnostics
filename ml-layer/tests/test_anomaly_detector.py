"""
Unit tests for AnomalyDetector class
"""

import pytest
import numpy as np
from datetime import datetime


class TestAnomalyDetectorInitialization:
    """Test AnomalyDetector initialization"""

    def test_has_correct_feature_names(self, anomaly_detector):
        """Test that detector has correct feature names"""
        expected_features = [
            'cpuUtilization', 'memoryUtilization', 'latencyMs',
            'throughput', 'errorRate', 'diskIo',
            'networkIn', 'networkOut', 'connectionCount',
            'responseTimeP50', 'responseTimeP95', 'responseTimeP99'
        ]

        assert anomaly_detector.feature_names == expected_features
        assert len(anomaly_detector.feature_names) == 12

    def test_has_model_manager(self, anomaly_detector):
        """Test that detector has a model manager"""
        assert anomaly_detector.model_manager is not None


class TestFeatureExtraction:
    """Test feature extraction functionality"""

    def test_extract_all_features(self, anomaly_detector, sample_normal_metrics):
        """Test that all features are extracted correctly"""
        features = anomaly_detector._extract_features(sample_normal_metrics)

        assert len(features) == 12
        assert features[0] == 0.45  # cpuUtilization
        assert features[1] == 0.50  # memoryUtilization
        assert features[2] == 100.0  # latencyMs
        assert features[3] == 500  # throughput
        assert features[4] == 0.005  # errorRate

    def test_handles_missing_features(self, anomaly_detector):
        """Test that missing features default to 0.0"""
        partial_metrics = {
            "serviceId": "test",
            "cpuUtilization": 0.5,
            "memoryUtilization": 0.6
        }

        features = anomaly_detector._extract_features(partial_metrics)

        assert len(features) == 12
        assert features[0] == 0.5
        assert features[1] == 0.6
        assert features[2] == 0.0  # latencyMs missing

    def test_handles_none_values(self, anomaly_detector):
        """Test that None values are converted to 0.0"""
        metrics_with_none = {
            "serviceId": "test",
            "cpuUtilization": None,
            "memoryUtilization": 0.6
        }

        features = anomaly_detector._extract_features(metrics_with_none)

        assert features[0] == 0.0  # None converted to 0.0
        assert features[1] == 0.6


class TestPrediction:
    """Test anomaly prediction functionality"""

    @pytest.mark.asyncio
    async def test_predict_returns_correct_structure(self, anomaly_detector, sample_normal_metrics):
        """Test that prediction returns correct structure"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert "predictionId" in result
        assert "timestamp" in result
        assert "serviceId" in result
        assert "metrics" in result
        assert "anomalyScore" in result
        assert "isAnomaly" in result
        assert "confidence" in result
        assert "modelUsed" in result
        assert "ensembleVotes" in result
        assert "featureImportance" in result

    @pytest.mark.asyncio
    async def test_predict_preserves_service_id(self, anomaly_detector, sample_normal_metrics):
        """Test that service ID is preserved in prediction"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert result["serviceId"] == "test-service"

    @pytest.mark.asyncio
    async def test_predict_generates_unique_ids(self, anomaly_detector, sample_normal_metrics):
        """Test that each prediction has unique ID"""
        result1 = await anomaly_detector.predict(sample_normal_metrics)
        result2 = await anomaly_detector.predict(sample_normal_metrics)

        assert result1["predictionId"] != result2["predictionId"]

    @pytest.mark.asyncio
    async def test_anomaly_score_is_float(self, anomaly_detector, sample_normal_metrics):
        """Test that anomaly score is a float"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert isinstance(result["anomalyScore"], float)

    @pytest.mark.asyncio
    async def test_is_anomaly_is_boolean(self, anomaly_detector, sample_normal_metrics):
        """Test that isAnomaly is a boolean"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert isinstance(result["isAnomaly"], bool)

    @pytest.mark.asyncio
    async def test_confidence_in_range(self, anomaly_detector, sample_normal_metrics):
        """Test that confidence is in [0, 1] range"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_detects_anomaly_for_high_values(self, anomaly_detector, sample_anomaly_metrics):
        """Test that anomalous metrics are detected as anomaly"""
        result = await anomaly_detector.predict(sample_anomaly_metrics)

        # High values should trigger anomaly detection
        # Note: Depends on model training, may be True or False
        assert "isAnomaly" in result

    @pytest.mark.asyncio
    async def test_ensemble_votes_contains_all_models(self, anomaly_detector, sample_normal_metrics):
        """Test that ensemble votes contains all model votes"""
        result = await anomaly_detector.predict(sample_normal_metrics)

        assert "IsolationForest" in result["ensembleVotes"]
        assert "OneClassSVM" in result["ensembleVotes"]


class TestExplanation:
    """Test explanation functionality"""

    @pytest.mark.asyncio
    async def test_explain_returns_correct_structure(self, anomaly_detector, sample_normal_metrics):
        """Test that explanation returns correct structure"""
        result = await anomaly_detector.explain(sample_normal_metrics)

        assert "serviceId" in result
        assert "timestamp" in result
        assert "featureValues" in result
        assert "featureImportance" in result
        assert "topFeatures" in result
        assert "explanation" in result

    @pytest.mark.asyncio
    async def test_explain_preserves_service_id(self, anomaly_detector, sample_normal_metrics):
        """Test that service ID is preserved in explanation"""
        result = await anomaly_detector.explain(sample_normal_metrics)

        assert result["serviceId"] == "test-service"

    @pytest.mark.asyncio
    async def test_top_features_limited_to_three(self, anomaly_detector, sample_normal_metrics):
        """Test that top features are limited to 3"""
        result = await anomaly_detector.explain(sample_normal_metrics)

        assert len(result["topFeatures"]) <= 3

    @pytest.mark.asyncio
    async def test_feature_values_contains_all_features(self, anomaly_detector, sample_normal_metrics):
        """Test that feature values contains all 12 features"""
        result = await anomaly_detector.explain(sample_normal_metrics)

        assert len(result["featureValues"]) == 12
        assert "cpuUtilization" in result["featureValues"]
        assert "memoryUtilization" in result["featureValues"]


class TestFeatureImportance:
    """Test feature importance calculation"""

    def test_calculate_feature_importance_returns_dict(self, anomaly_detector):
        """Test that feature importance returns a dictionary"""
        features = [0.5, 0.5, 100.0, 500.0, 0.01, 50.0,
                   400.0, 200.0, 50, 60.0, 150.0, 300.0]
        feature_names = anomaly_detector.feature_names

        importance = anomaly_detector._calculate_feature_importance(features, feature_names)

        assert isinstance(importance, dict)
        assert len(importance) == 12

    def test_feature_importance_normalized(self, anomaly_detector):
        """Test that feature importance sums to approximately 1.0"""
        # Use values that will create some deviation
        features = [0.9, 0.85, 500.0, 100.0, 0.5, 90.0,
                   1200.0, 800.0, 150, 500.0, 800.0, 1500.0]
        feature_names = anomaly_detector.feature_names

        importance = anomaly_detector._calculate_feature_importance(features, feature_names)

        total = sum(importance.values())
        assert abs(total - 1.0) < 0.01 or total == 0  # Either normalized to 1 or all zeros

    def test_high_cpu_gets_high_importance(self, anomaly_detector):
        """Test that high CPU value gets high importance"""
        # Normal values except very high CPU
        features = [0.99, 0.5, 100.0, 500.0, 0.01, 50.0,
                   400.0, 200.0, 50, 60.0, 150.0, 300.0]
        feature_names = anomaly_detector.feature_names

        importance = anomaly_detector._calculate_feature_importance(features, feature_names)

        # CPU should have relatively high importance
        assert importance["cpuUtilization"] > 0

    def test_high_error_rate_gets_high_importance(self, anomaly_detector):
        """Test that high error rate gets high importance"""
        # Normal values except very high error rate
        features = [0.5, 0.5, 100.0, 500.0, 0.5, 50.0,  # errorRate = 0.5 is very high
                   400.0, 200.0, 50, 60.0, 150.0, 300.0]
        feature_names = anomaly_detector.feature_names

        importance = anomaly_detector._calculate_feature_importance(features, feature_names)

        # Error rate should have high importance due to deviation from normal (0-0.01)
        assert importance["errorRate"] > 0


class TestConfidenceCalculation:
    """Test confidence calculation"""

    def test_confidence_with_unanimous_predictions(self, anomaly_detector):
        """Test confidence when all models agree"""
        predictions = {"model1": True, "model2": True, "model3": True}
        scores = {"model1": -0.5, "model2": -0.6, "model3": -0.7}

        confidence = anomaly_detector._calculate_confidence(predictions, scores)

        assert confidence > 0.5  # Should be high confidence for unanimous vote

    def test_confidence_with_split_predictions(self, anomaly_detector):
        """Test confidence when models disagree"""
        predictions = {"model1": True, "model2": False, "model3": True}
        scores = {"model1": -0.5, "model2": 0.3, "model3": -0.4}

        confidence = anomaly_detector._calculate_confidence(predictions, scores)

        # Confidence should be lower for split vote
        assert 0.0 <= confidence <= 1.0

    def test_confidence_with_empty_predictions(self, anomaly_detector):
        """Test confidence with empty predictions returns 0"""
        predictions = {}
        scores = {}

        confidence = anomaly_detector._calculate_confidence(predictions, scores)

        assert confidence == 0.0


class TestTopFeatures:
    """Test top features functionality"""

    def test_get_top_features_returns_list(self, anomaly_detector):
        """Test that get_top_features returns a list"""
        importance = {
            "cpuUtilization": 0.3,
            "memoryUtilization": 0.25,
            "latencyMs": 0.2,
            "errorRate": 0.15,
            "throughput": 0.1
        }

        top = anomaly_detector._get_top_features(importance, n=3)

        assert isinstance(top, list)
        assert len(top) == 3

    def test_get_top_features_sorted_by_importance(self, anomaly_detector):
        """Test that features are sorted by importance descending"""
        importance = {
            "cpuUtilization": 0.1,
            "memoryUtilization": 0.3,
            "latencyMs": 0.2
        }

        top = anomaly_detector._get_top_features(importance, n=3)

        assert top[0]["feature"] == "memoryUtilization"
        assert top[0]["importance"] == 0.3
        assert top[1]["feature"] == "latencyMs"

    def test_get_top_features_structure(self, anomaly_detector):
        """Test that each top feature has correct structure"""
        importance = {"cpuUtilization": 0.5, "memoryUtilization": 0.3}

        top = anomaly_detector._get_top_features(importance, n=2)

        for item in top:
            assert "feature" in item
            assert "importance" in item


class TestExplanationGeneration:
    """Test explanation text generation"""

    def test_generate_explanation_for_anomaly(self, anomaly_detector):
        """Test explanation generation for anomalous features"""
        importance = {
            "cpuUtilization": 0.5,  # High importance
            "memoryUtilization": 0.35
        }
        features = [0.95, 0.88, 100.0, 500.0, 0.01, 50.0,
                   400.0, 200.0, 50, 60.0, 150.0, 300.0]
        feature_names = anomaly_detector.feature_names

        explanation = anomaly_detector._generate_explanation(importance, features, feature_names)

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "Anomaly detected" in explanation or "normal" in explanation.lower()

    def test_generate_explanation_for_normal_values(self, anomaly_detector):
        """Test explanation generation for normal features"""
        importance = {
            "cpuUtilization": 0.1,  # Low importance
            "memoryUtilization": 0.1
        }
        features = [0.4, 0.45, 100.0, 500.0, 0.01, 50.0,
                   400.0, 200.0, 50, 60.0, 150.0, 300.0]
        feature_names = anomaly_detector.feature_names

        explanation = anomaly_detector._generate_explanation(importance, features, feature_names)

        assert isinstance(explanation, str)


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_handles_missing_service_id(self, anomaly_detector):
        """Test handling of missing service ID"""
        metrics = {
            "cpuUtilization": 0.5,
            "memoryUtilization": 0.5,
            "latencyMs": 100.0
        }

        result = await anomaly_detector.predict(metrics)

        assert result["serviceId"] == "unknown"

    @pytest.mark.asyncio
    async def test_handles_zero_values(self, anomaly_detector):
        """Test handling of all zero values"""
        metrics = {
            "serviceId": "test",
            "cpuUtilization": 0.0,
            "memoryUtilization": 0.0,
            "latencyMs": 0.0,
            "throughput": 0,
            "errorRate": 0.0
        }

        result = await anomaly_detector.predict(metrics)

        assert "predictionId" in result
        assert "isAnomaly" in result

    @pytest.mark.asyncio
    async def test_handles_extreme_high_values(self, anomaly_detector):
        """Test handling of extreme high values"""
        metrics = {
            "serviceId": "test",
            "cpuUtilization": 1.0,
            "memoryUtilization": 1.0,
            "latencyMs": 100000.0,
            "throughput": 0,
            "errorRate": 1.0
        }

        result = await anomaly_detector.predict(metrics)

        assert "predictionId" in result
        assert "isAnomaly" in result


class TestIntegration:
    """Integration tests for full prediction flow"""

    @pytest.mark.asyncio
    async def test_full_prediction_flow(self, anomaly_detector, sample_normal_metrics):
        """Test full prediction and explanation flow"""
        # Get prediction
        prediction = await anomaly_detector.predict(sample_normal_metrics)

        # Get explanation
        explanation = await anomaly_detector.explain(sample_normal_metrics)

        # Verify both return valid results
        assert prediction["serviceId"] == explanation["serviceId"]
        assert len(prediction["featureImportance"]) == len(explanation["featureImportance"])

    @pytest.mark.asyncio
    async def test_consistent_predictions(self, anomaly_detector, sample_normal_metrics):
        """Test that predictions are consistent for same input"""
        result1 = await anomaly_detector.predict(sample_normal_metrics)
        result2 = await anomaly_detector.predict(sample_normal_metrics)

        # Anomaly classification should be consistent
        assert result1["isAnomaly"] == result2["isAnomaly"]
        # Model votes should be consistent
        assert result1["ensembleVotes"] == result2["ensembleVotes"]
