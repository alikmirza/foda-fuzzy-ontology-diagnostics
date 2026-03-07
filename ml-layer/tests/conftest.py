"""
Pytest configuration and fixtures for FODA ML Service tests
"""

import pytest
import tempfile
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def temp_model_dir():
    """Create a temporary directory for model storage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_normal_metrics():
    """Sample metrics representing normal operation"""
    return {
        "serviceId": "test-service",
        "timestamp": "2025-12-14T12:00:00Z",
        "cpuUtilization": 0.45,
        "memoryUtilization": 0.50,
        "latencyMs": 100.0,
        "throughput": 500,
        "errorRate": 0.005,
        "diskIo": 50.0,
        "networkIn": 400.0,
        "networkOut": 200.0,
        "connectionCount": 40,
        "requestCount": 10000,
        "responseTimeP50": 60.0,
        "responseTimeP95": 150.0,
        "responseTimeP99": 300.0
    }


@pytest.fixture
def sample_anomaly_metrics():
    """Sample metrics representing anomalous operation"""
    return {
        "serviceId": "test-service-anomaly",
        "timestamp": "2025-12-14T12:00:00Z",
        "cpuUtilization": 0.95,
        "memoryUtilization": 0.92,
        "latencyMs": 5000.0,
        "throughput": 50,
        "errorRate": 0.45,
        "diskIo": 95.0,
        "networkIn": 1500.0,
        "networkOut": 900.0,
        "connectionCount": 200,
        "requestCount": 100000,
        "responseTimeP50": 2500.0,
        "responseTimeP95": 4500.0,
        "responseTimeP99": 8000.0
    }


@pytest.fixture
def sample_high_cpu_metrics():
    """Sample metrics with high CPU only"""
    return {
        "serviceId": "test-service-cpu",
        "timestamp": "2025-12-14T12:00:00Z",
        "cpuUtilization": 0.98,
        "memoryUtilization": 0.45,
        "latencyMs": 120.0,
        "throughput": 450,
        "errorRate": 0.008,
        "diskIo": 55.0,
        "networkIn": 380.0,
        "networkOut": 190.0,
        "connectionCount": 45,
        "requestCount": 12000,
        "responseTimeP50": 70.0,
        "responseTimeP95": 160.0,
        "responseTimeP99": 320.0
    }


@pytest.fixture
def sample_high_memory_metrics():
    """Sample metrics with high memory only"""
    return {
        "serviceId": "test-service-memory",
        "timestamp": "2025-12-14T12:00:00Z",
        "cpuUtilization": 0.40,
        "memoryUtilization": 0.97,
        "latencyMs": 180.0,
        "throughput": 400,
        "errorRate": 0.01,
        "diskIo": 60.0,
        "networkIn": 350.0,
        "networkOut": 180.0,
        "connectionCount": 50,
        "requestCount": 11000,
        "responseTimeP50": 90.0,
        "responseTimeP95": 200.0,
        "responseTimeP99": 400.0
    }


@pytest.fixture
def sample_latency_spike_metrics():
    """Sample metrics with latency spike"""
    return {
        "serviceId": "test-service-latency",
        "timestamp": "2025-12-14T12:00:00Z",
        "cpuUtilization": 0.55,
        "memoryUtilization": 0.60,
        "latencyMs": 8000.0,
        "throughput": 150,
        "errorRate": 0.02,
        "diskIo": 70.0,
        "networkIn": 600.0,
        "networkOut": 350.0,
        "connectionCount": 80,
        "requestCount": 15000,
        "responseTimeP50": 4000.0,
        "responseTimeP95": 7000.0,
        "responseTimeP99": 10000.0
    }


@pytest.fixture
def model_manager(temp_model_dir):
    """Create a ModelManager instance with temporary directory"""
    from ml.model_manager import ModelManager
    return ModelManager(model_dir=temp_model_dir)


@pytest.fixture
def anomaly_detector(model_manager):
    """Create an AnomalyDetector instance"""
    from ml.anomaly_detector import AnomalyDetector
    return AnomalyDetector(model_manager)
