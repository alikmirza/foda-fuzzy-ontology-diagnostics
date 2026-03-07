"""
Model Manager
Manages ML models for anomaly detection
"""

import os
import joblib
import logging
from typing import Dict, Optional
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
import numpy as np

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages training, loading, and saving of ML models
    """

    def __init__(self, model_dir: str = "/ml-models"):
        self.model_dir = model_dir
        self.models = {}
        self.scaler = StandardScaler()

        # Ensure model directory exists
        os.makedirs(model_dir, exist_ok=True)

        # Initialize or load models
        self._initialize_models()

    def _initialize_models(self):
        """
        Initialize or load pre-trained models
        """
        try:
            # Try to load existing models
            self._load_models()
            logger.info("Loaded existing models from disk")
        except Exception as e:
            logger.info(f"Creating new models: {e}")
            self._create_default_models()

    def _create_default_models(self):
        """
        Create default models with reasonable hyperparameters
        """
        logger.info("Creating default ML models...")

        # Isolation Forest
        self.models['IsolationForest'] = IsolationForest(
            n_estimators=100,
            max_samples='auto',
            contamination=0.1,
            random_state=42
        )

        # One-Class SVM
        self.models['OneClassSVM'] = OneClassSVM(
            kernel='rbf',
            gamma='auto',
            nu=0.1
        )

        # Train with synthetic normal data
        self._train_with_synthetic_data()

        logger.info("Default models created and trained")

    def _train_with_synthetic_data(self):
        """
        Train models with synthetic normal data
        """
        # Generate synthetic normal metrics
        np.random.seed(42)
        n_samples = 1000

        # Normal operating ranges
        normal_data = np.column_stack([
            np.random.uniform(0.2, 0.7, n_samples),  # CPU
            np.random.uniform(0.3, 0.7, n_samples),  # Memory
            np.random.uniform(50, 150, n_samples),   # Latency
            np.random.uniform(400, 700, n_samples),  # Throughput
            np.random.uniform(0, 0.01, n_samples),   # Error rate
            np.random.uniform(20, 80, n_samples),    # Disk IO
            np.random.uniform(100, 800, n_samples),  # Network In
            np.random.uniform(50, 400, n_samples),   # Network Out
            np.random.uniform(10, 80, n_samples),    # Connections
            np.random.uniform(30, 100, n_samples),   # P50
            np.random.uniform(100, 250, n_samples),  # P95
            np.random.uniform(200, 500, n_samples),  # P99
        ])

        # Fit scaler
        self.scaler.fit(normal_data)

        # Scale data
        scaled_data = self.scaler.transform(normal_data)

        # Train each model
        for model_name, model in self.models.items():
            try:
                logger.info(f"Training {model_name}...")
                model.fit(scaled_data)
                logger.info(f"{model_name} trained successfully")
            except Exception as e:
                logger.error(f"Failed to train {model_name}: {e}")

    async def train_models(self, training_data: Optional[Dict] = None) -> Dict:
        """
        Train or retrain models with provided data
        """
        try:
            if training_data is None:
                self._train_with_synthetic_data()
                result = {
                    "status": "success",
                    "message": "Models trained with synthetic data",
                    "models": list(self.models.keys())
                }
            else:
                # Train with provided data
                # TODO: Implement custom training data handling
                result = {
                    "status": "not_implemented",
                    "message": "Custom training data not yet implemented"
                }

            # Save models
            self._save_models()

            return result

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            raise

    def _save_models(self):
        """
        Save models to disk
        """
        try:
            for model_name, model in self.models.items():
                model_path = os.path.join(self.model_dir, f"{model_name}.joblib")
                joblib.dump(model, model_path)
                logger.info(f"Saved {model_name} to {model_path}")

            # Save scaler
            scaler_path = os.path.join(self.model_dir, "scaler.joblib")
            joblib.dump(self.scaler, scaler_path)
            logger.info(f"Saved scaler to {scaler_path}")

        except Exception as e:
            logger.error(f"Failed to save models: {e}", exc_info=True)

    def _load_models(self):
        """
        Load models from disk
        """
        model_files = {
            'IsolationForest': 'IsolationForest.joblib',
            'OneClassSVM': 'OneClassSVM.joblib'
        }

        for model_name, filename in model_files.items():
            model_path = os.path.join(self.model_dir, filename)
            if os.path.exists(model_path):
                self.models[model_name] = joblib.load(model_path)
                logger.info(f"Loaded {model_name} from {model_path}")

        # Load scaler
        scaler_path = os.path.join(self.model_dir, "scaler.joblib")
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            logger.info("Loaded scaler")

        if not self.models:
            raise FileNotFoundError("No models found on disk")

    def get_models(self) -> Dict:
        """
        Get all loaded models
        """
        return self.models

    def get_model_info(self) -> Dict:
        """
        Get information about current models
        """
        info = {
            "models": {},
            "scaler": {
                "mean": self.scaler.mean_.tolist() if hasattr(self.scaler, 'mean_') else None,
                "scale": self.scaler.scale_.tolist() if hasattr(self.scaler, 'scale_') else None
            }
        }

        for model_name, model in self.models.items():
            info["models"][model_name] = {
                "type": type(model).__name__,
                "parameters": model.get_params() if hasattr(model, 'get_params') else {}
            }

        return info
