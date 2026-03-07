"""
Unit tests for ModelManager class
"""

import pytest
import os
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM


class TestModelManagerInitialization:
    """Test ModelManager initialization"""

    def test_creates_model_directory(self, temp_model_dir):
        """Test that ModelManager creates model directory if it doesn't exist"""
        from ml.model_manager import ModelManager

        new_dir = os.path.join(temp_model_dir, "new_models")
        manager = ModelManager(model_dir=new_dir)

        assert os.path.exists(new_dir)

    def test_creates_default_models(self, model_manager):
        """Test that default models are created"""
        models = model_manager.get_models()

        assert "IsolationForest" in models
        assert "OneClassSVM" in models
        assert len(models) == 2

    def test_models_are_fitted(self, model_manager):
        """Test that models are properly fitted with training data"""
        models = model_manager.get_models()

        # Isolation Forest should have estimators after fitting
        iso_forest = models["IsolationForest"]
        assert hasattr(iso_forest, "estimators_")
        assert len(iso_forest.estimators_) > 0

        # OneClassSVM should have support vectors after fitting
        svm = models["OneClassSVM"]
        assert hasattr(svm, "support_")

    def test_scaler_is_fitted(self, model_manager):
        """Test that scaler is properly fitted"""
        assert hasattr(model_manager.scaler, "mean_")
        assert hasattr(model_manager.scaler, "scale_")
        assert model_manager.scaler.mean_ is not None
        assert model_manager.scaler.scale_ is not None
        # Should have 12 features
        assert len(model_manager.scaler.mean_) == 12


class TestModelManagerModelOperations:
    """Test model operations"""

    def test_get_models_returns_dict(self, model_manager):
        """Test that get_models returns a dictionary"""
        models = model_manager.get_models()
        assert isinstance(models, dict)

    def test_models_can_predict(self, model_manager):
        """Test that models can make predictions"""
        models = model_manager.get_models()

        # Create sample feature vector (12 features)
        sample = np.array([[0.5, 0.5, 100.0, 500.0, 0.01, 50.0,
                           400.0, 200.0, 50, 60.0, 150.0, 300.0]])

        for model_name, model in models.items():
            prediction = model.predict(sample)
            assert prediction is not None
            assert len(prediction) == 1
            assert prediction[0] in [-1, 1]  # sklearn convention

    def test_models_can_calculate_decision_function(self, model_manager):
        """Test that models can calculate decision function scores"""
        models = model_manager.get_models()

        sample = np.array([[0.5, 0.5, 100.0, 500.0, 0.01, 50.0,
                           400.0, 200.0, 50, 60.0, 150.0, 300.0]])

        for model_name, model in models.items():
            score = model.decision_function(sample)
            assert score is not None
            assert len(score) == 1
            assert isinstance(score[0], (int, float))


class TestModelManagerPersistence:
    """Test model save/load functionality"""

    def test_save_models_creates_files(self, model_manager, temp_model_dir):
        """Test that saving models creates joblib files"""
        model_manager._save_models()

        # Check that model files exist
        assert os.path.exists(os.path.join(temp_model_dir, "IsolationForest.joblib"))
        assert os.path.exists(os.path.join(temp_model_dir, "OneClassSVM.joblib"))
        assert os.path.exists(os.path.join(temp_model_dir, "scaler.joblib"))

    def test_load_models_restores_state(self, temp_model_dir):
        """Test that models can be loaded from disk"""
        from ml.model_manager import ModelManager

        # Create and save models
        manager1 = ModelManager(model_dir=temp_model_dir)
        manager1._save_models()

        # Create new manager and load models
        manager2 = ModelManager(model_dir=temp_model_dir)

        # Check models are loaded
        assert "IsolationForest" in manager2.get_models()
        assert "OneClassSVM" in manager2.get_models()


class TestModelManagerModelInfo:
    """Test model info functionality"""

    def test_get_model_info_returns_dict(self, model_manager):
        """Test that get_model_info returns proper structure"""
        info = model_manager.get_model_info()

        assert isinstance(info, dict)
        assert "models" in info
        assert "scaler" in info

    def test_model_info_contains_all_models(self, model_manager):
        """Test that model info contains all model details"""
        info = model_manager.get_model_info()

        assert "IsolationForest" in info["models"]
        assert "OneClassSVM" in info["models"]

        # Check model info structure
        for model_name, model_info in info["models"].items():
            assert "type" in model_info
            assert "parameters" in model_info

    def test_scaler_info_contains_statistics(self, model_manager):
        """Test that scaler info contains mean and scale"""
        info = model_manager.get_model_info()

        assert info["scaler"]["mean"] is not None
        assert info["scaler"]["scale"] is not None
        assert len(info["scaler"]["mean"]) == 12  # 12 features


class TestModelManagerTraining:
    """Test training functionality"""

    @pytest.mark.asyncio
    async def test_train_models_with_synthetic_data(self, model_manager):
        """Test training models with synthetic data"""
        result = await model_manager.train_models(training_data=None)

        assert result["status"] == "success"
        assert "IsolationForest" in result["models"]
        assert "OneClassSVM" in result["models"]

    @pytest.mark.asyncio
    async def test_train_models_saves_to_disk(self, model_manager, temp_model_dir):
        """Test that training saves models to disk"""
        await model_manager.train_models(training_data=None)

        # Check files exist
        assert os.path.exists(os.path.join(temp_model_dir, "IsolationForest.joblib"))
        assert os.path.exists(os.path.join(temp_model_dir, "OneClassSVM.joblib"))


class TestModelManagerEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_empty_model_directory(self, temp_model_dir):
        """Test that ModelManager handles missing models gracefully"""
        from ml.model_manager import ModelManager

        # Create manager with empty directory - should create default models
        manager = ModelManager(model_dir=temp_model_dir)

        assert len(manager.get_models()) > 0

    def test_isolation_forest_contamination(self, model_manager):
        """Test that Isolation Forest has proper contamination setting"""
        iso_forest = model_manager.get_models()["IsolationForest"]
        assert iso_forest.contamination == 0.1

    def test_svm_kernel_type(self, model_manager):
        """Test that OneClassSVM has RBF kernel"""
        svm = model_manager.get_models()["OneClassSVM"]
        assert svm.kernel == "rbf"
