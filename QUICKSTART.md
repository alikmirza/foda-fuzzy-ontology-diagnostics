# FODA Quick Start Guide

## 🎯 What's Been Built

You now have a **working foundation** for the FODA (Fuzzy-Ontology-based Diagnostic Architecture) system with:

✅ **3 Monitored Microservices** (Services A, B, C) - Spring Boot applications that collect and publish metrics
✅ **ML Anomaly Detection Service** - Python/FastAPI service with ensemble anomaly detection
✅ **Complete Infrastructure** - Docker Compose with Kafka, PostgreSQL, and Fuseki
✅ **~30% of total system** (Phases 0-2 of 6 complete)

## 🚀 Getting Started

### Prerequisites

Make sure you have installed:
- **Java 17+** (`java -version`)
- **Maven 3.8+** (`mvn -version`)
- **Python 3.11+** (`python --version`)
- **Docker & Docker Compose** (`docker --version`, `docker-compose --version`)

### Step 1: Start Infrastructure

```bash
cd /home/alik/IdeaProjects/foda-fuzzy-ontology-diagnostics

# Start Kafka, PostgreSQL, and Fuseki
docker-compose up -d zookeeper kafka postgres fuseki
```

Wait ~30 seconds for services to initialize. Check status:
```bash
docker-compose ps
```

### Step 2: Build Java Microservices

```bash
# Build all Java services
mvn clean install

# This will:
# - Compile Service-A, Service-B, Service-C
# - Run tests (if any)
# - Create JAR files in target/ directories
```

### Step 3: Start Microservices

**Option A: Using Docker (Recommended)**
```bash
docker-compose up -d service-a service-b service-c
```

**Option B: Using Maven (for development)**
```bash
# Terminal 1
cd microservices/service-a
mvn spring-boot:run

# Terminal 2
cd microservices/service-b
mvn spring-boot:run

# Terminal 3
cd microservices/service-c
mvn spring-boot:run
```

### Step 4: Start ML Service

**Option A: Using Docker**
```bash
docker-compose up -d ml-service
```

**Option B: Using Python directly**
```bash
cd ml-layer
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Step 5: Verify Everything is Running

```bash
# Check service health
curl http://localhost:8081/status  # Service A
curl http://localhost:8082/status  # Service B
curl http://localhost:8083/status  # Service C
curl http://localhost:8000/health  # ML Service
```

Expected response: JSON with status information

## 🧪 Testing the System

### Test 1: Get Current Metrics

```bash
curl http://localhost:8081/metrics
```

You should see JSON with CPU, memory, latency, throughput, etc.

### Test 2: Anomaly Detection

```bash
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
      "errorRate": 0.03,
      "diskIo": 85.0,
      "networkIn": 900.0,
      "networkOut": 450.0,
      "connectionCount": 95,
      "requestCount": 50000,
      "responseTimeP50": 120.0,
      "responseTimeP95": 320.0,
      "responseTimeP99": 580.0
    }
  }'
```

Expected response:
```json
{
  "predictionId": "uuid...",
  "timestamp": "2025-11-03T...",
  "serviceId": "service-a",
  "anomalyScore": -0.45,
  "isAnomaly": true,
  "confidence": 0.87,
  "modelUsed": "EnsembleVoting",
  "ensembleVotes": {
    "IsolationForest": true,
    "OneClassSVM": true
  },
  "featureImportance": {
    "cpuUtilization": 0.35,
    "latencyMs": 0.28,
    "errorRate": 0.15,
    ...
  }
}
```

### Test 3: Get Explanation

```bash
curl -X POST http://localhost:8000/explain \
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

### Test 4: Watch Kafka Messages (Optional)

```bash
# Install kafkacat if not already installed
# brew install kafkacat  (macOS)
# sudo apt install kafkacat  (Ubuntu)

# Watch metrics-stream topic
kafkacat -C -b localhost:9092 -t metrics-stream -f '\nKey: %k\nValue: %s\n'
```

You should see metrics being published every 10 seconds from each service.

## 📊 Monitoring

### Check Logs

```bash
# Docker logs
docker-compose logs -f service-a
docker-compose logs -f ml-service

# View all service logs
docker-compose logs -f
```

### Access Fuseki (RDF Store)

Open browser: http://localhost:3030

- Default user: `admin`
- Default password: `admin123`

### Access PostgreSQL

```bash
docker exec -it foda-postgres psql -U foda_user -d foda_metrics

# Query metrics
SELECT * FROM foda.service_metrics LIMIT 10;
```

## 🛑 Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

## 🐛 Troubleshooting

### Services won't start

```bash
# Check if ports are available
lsof -i :8081  # Service A
lsof -i :8082  # Service B
lsof -i :8083  # Service C
lsof -i :8000  # ML Service
lsof -i :9092  # Kafka
lsof -i :5432  # PostgreSQL
lsof -i :3030  # Fuseki

# Kill conflicting processes if needed
kill -9 <PID>
```

### Kafka connection errors

```bash
# Restart Kafka and Zookeeper
docker-compose restart zookeeper kafka

# Wait 30 seconds, then restart services
docker-compose restart service-a service-b service-c
```

### ML service errors

```bash
# Check Python dependencies
cd ml-layer
pip install -r requirements.txt

# Check logs
docker-compose logs ml-service
```

### Can't build Maven project

```bash
# Clean and rebuild
mvn clean
mvn install -DskipTests

# If still failing, check Java version
java -version  # Should be 17+
```

## 📚 Next Steps

Now that you have the foundation running, you can:

1. **Enable anomaly simulation**:
   ```bash
   # Edit microservices/service-a/src/main/resources/application.yml
   # Set: metrics.anomaly.simulation: true
   ```

2. **Implement Phase 3: Fuzzy Diagnostic Engine**
   - See README.md "Next Steps" section
   - Create fuzzy-engine module
   - Define fuzzy rules
   - Integrate with ML service

3. **Add Kafka consumers to ML service**
   - Consume from `metrics-stream` topic
   - Publish to `ml-predictions` topic

4. **Develop Phase 4: Ontology Integration**
   - Design DiagnosticKB.owl in Protégé
   - Implement ontology mapper
   - Store explanations in Fuseki

## 📖 Documentation

- **Architecture**: See `foda_ml_architecture.drawio`
- **Full Spec**: See `Hybrid Java-based FODA Architecture & Development.pdf`
- **Project Structure**: See `README.md`

## 💬 Need Help?

Check logs first:
```bash
docker-compose logs -f
```

Common issues and solutions are in the Troubleshooting section above.

---

**Status**: Phase 0-2 Complete (30%) | Ready for Phase 3: Fuzzy Diagnostic Engine
