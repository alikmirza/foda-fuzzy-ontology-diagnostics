# FODA Ontology Mapper Service

**Part of:** FODA - Fuzzy-Ontology-based Diagnostic Architecture
**Phase:** 4 - Ontology Integration
**Version:** 1.0.0-SNAPSHOT
**Port:** 8085

## Overview

The Ontology Mapper Service is responsible for converting diagnostic results from the Fuzzy Engine into RDF triples and storing them in the Apache Jena Fuseki triple store. It provides semantic knowledge representation and SPARQL-based querying capabilities for the FODA system.

## Key Features

- **Automatic RDF Conversion**: Converts diagnostic results to RDF triples using DiagnosticKB ontology
- **Fuseki Integration**: Stores and retrieves diagnostic knowledge from Apache Jena Fuseki
- **SPARQL Query Service**: Provides predefined and custom SPARQL queries
- **Kafka Integration**: Consumes diagnostic events from Kafka
- **REST API**: Exposes ontology query endpoints
- **Semantic Reasoning**: Links diagnostics, faults, recommendations, and services

## Architecture

```
Kafka (diagnostic-events)
         ↓
  DiagnosticConsumer
         ↓
   DiagnosticMapper (Java → RDF)
         ↓
    FusekiService
         ↓
Apache Jena Fuseki (Triple Store)
         ↓
  SparqlQueryService
         ↓
    QueryController (REST API)
```

## Components

### Core Services

1. **OntologyLoader** - Loads DiagnosticKB.owl ontology at startup
2. **DiagnosticMapper** - Maps Java POJOs to RDF triples
3. **FusekiService** - Manages Fuseki connections and operations
4. **SparqlQueryService** - Provides SPARQL query templates

### Kafka

- **Topic:** `diagnostic-events`
- **Consumer Group:** `ontology-mapper-group`
- **Message Format:** DiagnosticResult JSON

### Ontology Schema

**Namespace:** `http://foda.com/ontology/diagnostic#`

**Key Classes:**
- `MicroService` - Represents a microservice instance
- `DiagnosticResult` - Result of fuzzy diagnostic analysis
- `Fault` - Fault type (CPU Saturation, Memory Leak, etc.)
- `Anomaly` - ML-detected anomaly
- `Recommendation` - Remediation recommendation
- `Severity` - Severity level (Low, Medium, High, Critical)
- `ContributingFactor` - Factors contributing to a fault

**Key Properties:**
- `diagnosedAs` - Links anomaly to fault type
- `affectsService` - Links fault to service
- `hasRecommendation` - Links fault to recommendations
- `hasSeverity` - Links fault to severity level
- `fci` - Fuzzy Confidence Index value

## REST API Endpoints

### Query Diagnostics

```bash
# Get diagnostics for a service
GET /ontology/diagnostics/service/{serviceId}

# Get diagnostics by fault type
GET /ontology/diagnostics/fault/{faultType}
# Example: /ontology/diagnostics/fault/CpuSaturation

# Get diagnostics by severity
GET /ontology/diagnostics/severity/{severity}
# Example: /ontology/diagnostics/severity/Critical

# Get diagnostic details
GET /ontology/diagnostics/{diagnosticId}

# Get recommendations for a diagnostic
GET /ontology/diagnostics/{diagnosticId}/recommendations

# Get contributing factors
GET /ontology/diagnostics/{diagnosticId}/factors

# Get recent diagnostics
GET /ontology/diagnostics/recent?limit=10
```

### Statistics

```bash
# Get fault statistics
GET /ontology/statistics/faults
```

### Custom Queries

```bash
# Execute custom SPARQL query
POST /ontology/query/sparql
Content-Type: text/plain

PREFIX diagnostic: <http://foda.com/ontology/diagnostic#>
SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10
```

### Health Check

```bash
GET /ontology/health
```

## Example SPARQL Queries

### Get All Diagnostics for Service A

```sparql
PREFIX diagnostic: <http://foda.com/ontology/diagnostic#>

SELECT ?diagnosticId ?timestamp ?faultType ?severity ?fci
WHERE {
    ?service diagnostic:serviceId "service-a" .
    ?service diagnostic:hasDiagnosis ?diagnostic .
    ?diagnostic diagnostic:diagnosticId ?diagnosticId .
    ?diagnostic diagnostic:timestamp ?timestamp .
    ?diagnostic diagnostic:diagnosedAs ?fault .
    ?diagnostic diagnostic:hasSeverity ?sev .
    ?diagnostic diagnostic:fci ?fci .
    ?fault rdf:type ?faultType .
}
ORDER BY DESC(?timestamp)
```

### Get Critical Faults

```sparql
PREFIX diagnostic: <http://foda.com/ontology/diagnostic#>

SELECT ?diagnosticId ?serviceId ?faultType ?fci
WHERE {
    ?diagnostic diagnostic:hasSeverity diagnostic:Critical .
    ?diagnostic diagnostic:diagnosticId ?diagnosticId .
    ?diagnostic diagnostic:fci ?fci .
    ?diagnostic diagnostic:diagnosedAs ?fault .
    ?service diagnostic:hasDiagnosis ?diagnostic .
    ?service diagnostic:serviceId ?serviceId .
    ?fault rdf:type ?faultType .
}
ORDER BY DESC(?fci)
```

### Get Fault Statistics

```sparql
PREFIX diagnostic: <http://foda.com/ontology/diagnostic#>

SELECT ?faultType (COUNT(?diagnostic) AS ?count)
WHERE {
    ?diagnostic diagnostic:diagnosedAs ?fault .
    ?fault rdf:type ?faultType .
    FILTER(?faultType != <http://foda.com/ontology/diagnostic#Fault>)
}
GROUP BY ?faultType
ORDER BY DESC(?count)
```

## Configuration

### Application Properties

```yaml
server:
  port: 8085

spring:
  kafka:
    bootstrap-servers: ${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
    consumer:
      group-id: ontology-mapper-group

fuseki:
  endpoint: ${FUSEKI_ENDPOINT:http://localhost:3030/foda}

ontology:
  file:
    path: ${ONTOLOGY_PATH:classpath:ontology/DiagnosticKB.owl}
```

### Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS` - Kafka bootstrap servers
- `FUSEKI_ENDPOINT` - Fuseki SPARQL endpoint
- `ONTOLOGY_PATH` - Path to DiagnosticKB.owl file

## Building

```bash
# Build with Maven
mvn clean install

# Run locally
mvn spring-boot:run

# Build Docker image
docker build -t foda/ontology-mapper:latest -f Dockerfile ../
```

## Running

### With Docker Compose

```bash
docker-compose up -d ontology-mapper
```

### Standalone

```bash
# Ensure Kafka and Fuseki are running
docker-compose up -d kafka fuseki

# Run the service
java -jar target/ontology-mapper-1.0.0-SNAPSHOT.jar
```

## Testing

### Check Health

```bash
curl http://localhost:8085/ontology/health
```

Expected response:
```json
{
  "status": "UP",
  "service": "ontology-mapper",
  "fusekiAvailable": true,
  "tripleCount": 0,
  "timestamp": "2025-12-07T..."
}
```

### Query Recent Diagnostics

```bash
curl http://localhost:8085/ontology/diagnostics/recent?limit=5
```

### Execute Custom SPARQL

```bash
curl -X POST http://localhost:8085/ontology/query/sparql \
  -H "Content-Type: text/plain" \
  -d "PREFIX diagnostic: <http://foda.com/ontology/diagnostic#>
      SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
```

## Dependencies

- **Spring Boot 3.2.0** - Application framework
- **Apache Jena 4.10.0** - RDF/OWL processing
  - jena-core - Core RDF functionality
  - jena-arq - SPARQL query engine
  - jena-tdb2 - Triple store
  - jena-rdfconnection - Fuseki connectivity
- **OWL API 5.5.0** - OWL ontology processing
- **Spring Kafka** - Kafka integration
- **Lombok** - Code generation

## Troubleshooting

### Fuseki Connection Error

```
Error: Failed to connect to Fuseki
```

**Solution:**
- Ensure Fuseki is running: `docker-compose ps fuseki`
- Check Fuseki endpoint: `curl http://localhost:3030/$/ping`
- Verify network connectivity

### Ontology Loading Error

```
Error: Failed to load diagnostic ontology
```

**Solution:**
- Verify DiagnosticKB.owl exists in resources
- Check ontology file path configuration
- Validate OWL syntax using Protégé

### No Triples Stored

```
Health check shows tripleCount: 0
```

**Solution:**
- Verify Kafka consumer is receiving messages
- Check diagnostic-events topic has messages
- Review application logs for errors

## Logging

View logs:
```bash
# Docker
docker-compose logs -f ontology-mapper

# Local
tail -f logs/ontology-mapper.log
```

Log levels:
- `com.foda.ontology` - INFO
- `org.apache.jena` - WARN
- `org.springframework.kafka` - INFO

## Future Enhancements

- [ ] Semantic reasoning with OWL reasoner
- [ ] Inference rules for fault diagnosis
- [ ] Time-series diagnostic trend analysis
- [ ] Root cause analysis using RDF paths
- [ ] Explanation generation service
- [ ] Graph visualization endpoints

## License

Apache License 2.0

## Related Services

- **Fuzzy Engine** (port 8084) - Upstream diagnostic service
- **Apache Jena Fuseki** (port 3030) - RDF triple store
- **Kafka** (port 9092) - Message broker

---

**Part of FODA System** | Phase 4 Complete ✅ | v1.0.0
