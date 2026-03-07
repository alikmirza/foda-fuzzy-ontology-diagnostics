# FODA - Fuzzy-Ontology-based Diagnostic Architecture

🎯 **A novel hybrid diagnostic architecture that integrates machine learning, fuzzy logic, and semantic ontologies for accurate, interpretable, and confidence-graded fault diagnostics in distributed microservices systems.**

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Implementation Status](#implementation-status)
- [Development Roadmap](#development-roadmap)
- [Technologies](#technologies)
- [Next Steps](#next-steps)
- [License](#license)

## 🎯 Overview

Traditional distributed system diagnostics suffer from two key limitations:

- **Threshold-based systems** produce binary alerts without handling uncertainty
- **ML-based systems** operate as black boxes without explainability

FODA addresses both by combining:

- 🤖 **Machine Learning** for data-driven anomaly detection
- 🌫️ **Fuzzy Logic** for uncertainty handling and linguistic representation
- 🧠 **Semantic Ontologies** for structured, explainable reasoning

## ✅ What Has Been Implemented

### Phase 0-2 Complete (Weeks 1-6 of 16)

#### ✅ Infrastructure & Setup
- Complete Docker Compose configuration with:
  - Apache Kafka & Zookeeper
  - PostgreSQL database with initialized schema
  - Apache Jena Fuseki (RDF triple store)
  - Container networking and volume management
- Maven parent POM with full dependency management
- Comprehensive .gitignore for Java, Python, Node, and ML artifacts

#### ✅ Monitored Microservices (Services A, B, C)
Three identical Spring Boot 3.x microservices that:
- **Collect real system metrics**: CPU, memory, latency, throughput, error rate, disk I/O, network, connections, response time percentiles
- **Publish to Kafka**: Automatic metrics streaming every 10 seconds to `metrics-stream` topic
- **Expose REST endpoints**:
  - `GET /metrics` - Current service metrics
  - `GET /status` - Service health and uptime
  - `POST /diagnose/collect` - Manual metrics trigger
  - `GET /diagnose/summary` - Diagnostic summary
- **Anomaly simulation mode**: Configurable flag to inject synthetic anomalies
- **Dockerized**: Multi-stage builds with health checks

#### ✅ Python ML Anomaly Detection Service
FastAPI-based ML service featuring:
- **Ensemble anomaly detection**: Isolation Forest + One-Class SVM
- **Model Manager**: Auto-trains models with synthetic data, supports save/load
- **Feature extraction**: 12-dimensional feature vectors from service metrics
- **Ensemble voting**: Majority voting across multiple models
- **Confidence scoring**: Based on model agreement and score magnitudes
- **Feature importance**: Deviation-based importance calculation
- **REST API**:
  - `POST /predict` - Anomaly detection with confidence scores
  - `POST /explain` - Feature importance and explanations
  - `POST /train` - Model training/retraining
  - `GET /model-info` - Model metadata
  - `GET /health` - Health check
- **Dockerized**: Python 3.11-slim with all dependencies

## 📁 Project Structure (Current)

```
foda-fuzzy-ontology-diagnostics/
│
├── docker-compose.yml              # Complete infrastructure setup
├── pom.xml                         # Parent Maven POM
├── scripts/
│   └── init-db.sql                # PostgreSQL initialization
│
├── microservices/                  # ✅ COMPLETE
│   ├── service-a/
│   │   ├── pom.xml
│   │   ├── Dockerfile
│   │   └── src/main/
│   │       ├── java/com/foda/service/
│   │       │   ├── ServiceAApplication.java
│   │       │   ├── config/
│   │       │   │   └── KafkaProducerConfig.java
│   │       │   ├── controller/
│   │       │   │   ├── MetricsController.java
│   │       │   │   ├── StatusController.java
│   │       │   │   └── DiagnoseController.java
│   │       │   ├── service/
│   │       │   │   └── MetricsCollectorService.java
│   │       │   ├── kafka/
│   │       │   │   └── MetricsProducer.java
│   │       │   └── model/
│   │       │       ├── ServiceMetrics.java
│   │       │       └── ServiceStatus.java
│   │       └── resources/
│   │           └── application.yml
│   ├── service-b/                  # (Same structure)
│   └── service-c/                  # (Same structure)
│
└── ml-layer/                       # ✅ COMPLETE (Core)
    ├── Dockerfile
    ├── requirements.txt
    ├── models/                     # Trained model storage
    └── src/
        ├── main.py                # FastAPI application
        └── ml/
            ├── anomaly_detector.py # Ensemble detector
            └── model_manager.py   # Model lifecycle management
```

## 🚀 Quick Start

### Prerequisites

- Java 17+
- Python 3.11+
- Docker & Docker Compose
- Maven 3.8+

### Build & Run

```bash
# 1. Start infrastructure
docker-compose up -d kafka postgres fuseki

# 2. Build Java services
mvn clean install

# 3. Start services
docker-compose up service-a service-b service-c

# 4. Start ML service
docker-compose up ml-service
```

### Test Endpoints

```bash
# Check service health
curl http://localhost:8081/status
curl http://localhost:8082/status
curl http://localhost:8083/status

# Get current metrics
curl http://localhost:8081/metrics

# ML service health
curl http://localhost:8000/health

# Test anomaly detection
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": {
      "serviceId": "service-a",
      "timestamp": "2025-11-03T12:00:00Z",
      "cpuUtilization": 0.95,
      "memoryUtilization": 0.87,
      "latencyMs": 450,
      "throughput": 250,
      "errorRate": 0.03
    }
  }'
```

## 🗺️ Development Roadmap

| Phase | Duration | Status | Progress |
|-------|----------|--------|----------|
| Phase 0: Setup & Preparation | 1 week | ✅ Complete | 100% |
| Phase 1: Microservices | 2 weeks | ✅ Complete | 100% |
| Phase 2: Python ML Detector | 3 weeks | ✅ Complete | 85% |
| Phase 3: Fuzzy Engine | 3 weeks | 📋 Pending | 0% |
| Phase 4: Ontology Integration | 3 weeks | 📋 Pending | 0% |
| Phase 5: API & Dashboard | 2 weeks | 📋 Pending | 0% |
| Phase 6: Evaluation | 3 weeks | 📋 Pending | 0% |
| **Total** | **16 weeks** | **🚧 In Progress** | **~30%** |

## 📋 Next Steps (Phase 3: Fuzzy Diagnostic Engine)

To continue development, implement the Fuzzy Diagnostic Engine:

1. **Create fuzzy-engine module** (Spring Boot 3.x)
2. **Add jFuzzyLogic dependency** (3.0)
3. **Define fuzzy rules** (.fcl files):
   - IF anomalyScore=HIGH AND cpu=HIGH THEN diagnosis=ResourceContention
   - 15-20 rules covering common fault types
4. **Implement FuzzyInferenceService**:
   - Consume ML predictions from Kafka `ml-predictions` topic
   - Apply fuzzy rules to classify fault types
   - Calculate FCI (Fuzzy Confidence Index)
   - Generate diagnostic explanation payloads
5. **Implement DiagnosticEventPublisher**:
   - Publish diagnostic results to Kafka `diagnostic-events` topic
6. **Add REST endpoints**:
   - `POST /fuzzy/diagnose` - Manual fuzzy diagnosis
   - `GET /fuzzy/rules` - List active fuzzy rules
   - `GET /fuzzy/confidence/{id}` - Get FCI for diagnosis

## 🛠️ Technologies Used

- **Java 17** + Spring Boot 3.2.0
- **Python 3.11** + FastAPI 0.104.1
- **scikit-learn 1.3.2** (Isolation Forest, One-Class SVM)
- **Apache Kafka 3.6.0**
- **PostgreSQL 15**
- **Apache Jena Fuseki 4.9.0**
- **Docker & Docker Compose**

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE)

---

**Implementation Progress**: Phase 0-2 Complete (6/16 weeks) | Next: Fuzzy Diagnostic Engine
