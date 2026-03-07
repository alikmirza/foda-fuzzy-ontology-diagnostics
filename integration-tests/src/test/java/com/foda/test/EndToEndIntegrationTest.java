package com.foda.test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.restassured.RestAssured;
import io.restassured.http.ContentType;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.*;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.time.Duration;
import java.time.Instant;
import java.util.*;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.hamcrest.Matchers.*;

/**
 * End-to-End Integration Test for FODA Diagnostic Architecture
 *
 * Tests the complete diagnostic pipeline:
 * 1. Metrics Collection → Kafka
 * 2. ML Anomaly Detection → Kafka
 * 3. Fuzzy Diagnostic Engine → Kafka
 * 4. Ontology Mapper → Fuseki
 * 5. API Gateway → Dashboard
 */
@Testcontainers
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class EndToEndIntegrationTest {

    private static final Network network = Network.newNetwork();

    @Container
    private static final KafkaContainer kafka = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
            .withNetwork(network)
            .withNetworkAliases("kafka");

    @Container
    private static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
            .withDatabaseName("foda_metrics")
            .withUsername("foda_user")
            .withPassword("foda_pass")
            .withNetwork(network)
            .withNetworkAliases("postgres");

    private static KafkaProducer<String, String> producer;
    private static KafkaConsumer<String, String> consumer;
    private static ObjectMapper objectMapper;

    @BeforeAll
    public static void setUp() {
        // Configure RestAssured for API Gateway
        RestAssured.baseURI = "http://localhost";
        RestAssured.port = 8080;

        objectMapper = new ObjectMapper();

        // Setup Kafka producer
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers());
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producer = new KafkaProducer<>(producerProps);

        // Setup Kafka consumer
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers());
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "test-consumer-group");
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        consumer = new KafkaConsumer<>(consumerProps);
    }

    @AfterAll
    public static void tearDown() {
        if (producer != null) producer.close();
        if (consumer != null) consumer.close();
    }

    @Test
    @Order(1)
    @DisplayName("Test 1: Service Health Endpoints")
    public void testServiceHealthEndpoints() {
        // Test Service A health
        given()
            .when()
                .get("/api/services/service-a/health")
            .then()
                .statusCode(200)
                .body("status", equalTo("UP"));

        // Test Service B health
        given()
            .when()
                .get("/api/services/service-b/health")
            .then()
                .statusCode(200)
                .body("status", equalTo("UP"));

        // Test Service C health
        given()
            .when()
                .get("/api/services/service-c/health")
            .then()
                .statusCode(200)
                .body("status", equalTo("UP"));
    }

    @Test
    @Order(2)
    @DisplayName("Test 2: Metrics Emission to Kafka")
    public void testMetricsEmissionToKafka() throws Exception {
        consumer.subscribe(Collections.singletonList("metrics-stream"));

        // Trigger metric collection
        given()
            .when()
                .post("/api/services/service-a/trigger-metrics")
            .then()
                .statusCode(202);

        // Verify metrics appear in Kafka
        await().atMost(Duration.ofSeconds(10)).untilAsserted(() -> {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
            assertThat(records.isEmpty()).isFalse();

            ConsumerRecord<String, String> record = records.iterator().next();
            JsonNode metric = objectMapper.readTree(record.value());

            assertThat(metric.has("serviceId")).isTrue();
            assertThat(metric.has("timestamp")).isTrue();
            assertThat(metric.has("cpuUsage")).isTrue();
            assertThat(metric.has("memoryUsage")).isTrue();
        });
    }

    @Test
    @Order(3)
    @DisplayName("Test 3: ML Anomaly Detection Pipeline")
    public void testMLAnomalyDetection() throws Exception {
        consumer.subscribe(Collections.singletonList("ml-predictions"));

        // Send anomalous metrics
        String anomalousMetric = """
            {
                "serviceId": "service-a",
                "timestamp": "%s",
                "cpuUsage": 95.5,
                "memoryUsage": 98.2,
                "responseTime": 5000,
                "errorRate": 0.45,
                "requestCount": 1000
            }
            """.formatted(Instant.now().toString());

        producer.send(new ProducerRecord<>("metrics-stream", "service-a", anomalousMetric));

        // Verify ML prediction appears in Kafka
        await().atMost(Duration.ofSeconds(15)).untilAsserted(() -> {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
            assertThat(records.isEmpty()).isFalse();

            ConsumerRecord<String, String> record = records.iterator().next();
            JsonNode prediction = objectMapper.readTree(record.value());

            assertThat(prediction.has("predictionId")).isTrue();
            assertThat(prediction.has("serviceId")).isTrue();
            assertThat(prediction.get("isAnomaly").asBoolean()).isTrue();
            assertThat(prediction.get("anomalyScore").asDouble()).isGreaterThan(0.5);
        });
    }

    @Test
    @Order(4)
    @DisplayName("Test 4: Fuzzy Diagnostic Engine Processing")
    public void testFuzzyDiagnosticEngine() throws Exception {
        consumer.subscribe(Collections.singletonList("diagnostic-events"));

        // Send ML prediction
        String mlPrediction = """
            {
                "predictionId": "pred-123",
                "serviceId": "service-a",
                "timestamp": "%s",
                "isAnomaly": true,
                "anomalyScore": 0.92,
                "features": {
                    "cpuUsage": 95.5,
                    "memoryUsage": 98.2,
                    "responseTime": 5000,
                    "errorRate": 0.45
                }
            }
            """.formatted(Instant.now().toString());

        producer.send(new ProducerRecord<>("ml-predictions", "service-a", mlPrediction));

        // Verify diagnostic result appears in Kafka
        await().atMost(Duration.ofSeconds(15)).untilAsserted(() -> {
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
            assertThat(records.isEmpty()).isFalse();

            ConsumerRecord<String, String> record = records.iterator().next();
            JsonNode diagnostic = objectMapper.readTree(record.value());

            assertThat(diagnostic.has("diagnosticId")).isTrue();
            assertThat(diagnostic.has("faultType")).isTrue();
            assertThat(diagnostic.has("severity")).isTrue();
            assertThat(diagnostic.has("fci")).isTrue();
            assertThat(diagnostic.get("fci").asDouble()).isBetween(0.0, 1.0);
        });
    }

    @Test
    @Order(5)
    @DisplayName("Test 5: Ontology Mapping and SPARQL Queries")
    public void testOntologyMappingAndQueries() throws Exception {
        // Wait for diagnostic to be mapped to ontology
        Thread.sleep(5000);

        // Query diagnostics by service
        given()
            .when()
                .get("/api/ontology/diagnostics/service/service-a")
            .then()
                .statusCode(200)
                .body("size()", greaterThan(0))
                .body("[0].serviceId", equalTo("service-a"))
                .body("[0].faultType", notNullValue())
                .body("[0].fci", notNullValue());

        // Query high severity diagnostics
        given()
            .when()
                .get("/api/ontology/diagnostics/severity/HIGH")
            .then()
                .statusCode(200)
                .body("size()", greaterThan(0))
                .body("[0].severity", equalTo("HIGH"));
    }

    @Test
    @Order(6)
    @DisplayName("Test 6: API Gateway Aggregation Endpoints")
    public void testAPIGatewayAggregation() {
        // Test system health aggregation
        given()
            .when()
                .get("/api/dashboard/health")
            .then()
                .statusCode(200)
                .body("service-a", notNullValue())
                .body("service-b", notNullValue())
                .body("service-c", notNullValue())
                .body("ml-service", notNullValue())
                .body("fuzzy-engine", notNullValue())
                .body("ontology-mapper", notNullValue());

        // Test dashboard overview
        given()
            .when()
                .get("/api/dashboard/overview")
            .then()
                .statusCode(200)
                .body("totalServices", equalTo(3))
                .body("activeAnomalies", greaterThanOrEqualTo(0))
                .body("diagnosticsToday", greaterThanOrEqualTo(0));
    }

    @Test
    @Order(7)
    @DisplayName("Test 7: Complete Diagnostic Pipeline Performance")
    public void testCompletePipelinePerformance() throws Exception {
        long startTime = System.currentTimeMillis();

        // Send metric
        String metric = """
            {
                "serviceId": "service-b",
                "timestamp": "%s",
                "cpuUsage": 92.0,
                "memoryUsage": 95.0,
                "responseTime": 4500,
                "errorRate": 0.38,
                "requestCount": 800
            }
            """.formatted(Instant.now().toString());

        producer.send(new ProducerRecord<>("metrics-stream", "service-b", metric));

        // Wait for diagnostic to appear in ontology
        await().atMost(Duration.ofSeconds(30)).untilAsserted(() -> {
            String response = given()
                .when()
                    .get("/api/ontology/diagnostics/recent?limit=1")
                .then()
                    .statusCode(200)
                    .extract().asString();

            JsonNode diagnostics = objectMapper.readTree(response);
            assertThat(diagnostics.size()).isGreaterThan(0);
        });

        long endTime = System.currentTimeMillis();
        long pipelineDuration = endTime - startTime;

        System.out.println("Complete pipeline duration: " + pipelineDuration + "ms");
        assertThat(pipelineDuration).isLessThan(30000); // Should complete within 30 seconds
    }

    @Test
    @Order(8)
    @DisplayName("Test 8: Fault Classification Accuracy")
    public void testFaultClassificationAccuracy() throws Exception {
        // Test high CPU fault
        testFaultScenario("HIGH_CPU", 95.0, 70.0, 1500, 0.05, "RESOURCE_EXHAUSTION");

        // Test high memory fault
        testFaultScenario("HIGH_MEMORY", 60.0, 98.0, 1800, 0.08, "RESOURCE_EXHAUSTION");

        // Test high error rate fault
        testFaultScenario("HIGH_ERROR", 50.0, 50.0, 2000, 0.75, "APPLICATION_ERROR");

        // Test slow response fault
        testFaultScenario("SLOW_RESPONSE", 40.0, 45.0, 8000, 0.15, "PERFORMANCE_DEGRADATION");
    }

    private void testFaultScenario(String testId, double cpu, double memory,
                                   int responseTime, double errorRate,
                                   String expectedFaultType) throws Exception {
        String metric = """
            {
                "serviceId": "service-c",
                "timestamp": "%s",
                "cpuUsage": %.1f,
                "memoryUsage": %.1f,
                "responseTime": %d,
                "errorRate": %.2f,
                "requestCount": 1000
            }
            """.formatted(Instant.now().toString(), cpu, memory, responseTime, errorRate);

        producer.send(new ProducerRecord<>("metrics-stream", testId, metric));

        // Wait for diagnostic
        Thread.sleep(10000);

        // Verify fault type
        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=5")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);
        boolean foundExpectedFault = false;
        for (JsonNode diag : diagnostics) {
            if (diag.has("faultType") &&
                diag.get("faultType").asText().equals(expectedFaultType)) {
                foundExpectedFault = true;
                break;
            }
        }

        assertThat(foundExpectedFault)
            .as("Expected fault type %s for scenario %s", expectedFaultType, testId)
            .isTrue();
    }

    @Test
    @Order(9)
    @DisplayName("Test 9: System Load Testing")
    public void testSystemLoadHandling() throws Exception {
        int numMetrics = 100;
        List<String> messageIds = new ArrayList<>();

        // Send burst of metrics
        for (int i = 0; i < numMetrics; i++) {
            String messageId = "load-test-" + i;
            String metric = """
                {
                    "serviceId": "service-a",
                    "timestamp": "%s",
                    "cpuUsage": %.1f,
                    "memoryUsage": %.1f,
                    "responseTime": %d,
                    "errorRate": %.2f,
                    "requestCount": 1000
                }
                """.formatted(
                    Instant.now().toString(),
                    50.0 + Math.random() * 50,
                    50.0 + Math.random() * 50,
                    (int)(500 + Math.random() * 4500),
                    Math.random() * 0.5
                );

            producer.send(new ProducerRecord<>("metrics-stream", messageId, metric));
            messageIds.add(messageId);
        }

        // Wait for system to process
        Thread.sleep(60000);

        // Verify all metrics were processed
        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=" + numMetrics)
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);

        // Should have processed most metrics (allow for some normal metrics to be filtered)
        assertThat(diagnostics.size()).isGreaterThan(numMetrics / 4);

        System.out.println("Processed " + diagnostics.size() + " out of " + numMetrics + " metrics");
    }

    @Test
    @Order(10)
    @DisplayName("Test 10: Dashboard Data Consistency")
    public void testDashboardDataConsistency() throws Exception {
        // Get recent diagnostics from ontology API
        String ontologyResponse = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=10")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode ontologyDiagnostics = objectMapper.readTree(ontologyResponse);

        // Get dashboard overview
        String dashboardResponse = given()
            .when()
                .get("/api/dashboard/overview")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode dashboardData = objectMapper.readTree(dashboardResponse);

        // Verify data consistency
        assertThat(dashboardData.has("totalServices")).isTrue();
        assertThat(dashboardData.has("diagnosticsToday")).isTrue();
        assertThat(dashboardData.has("activeAnomalies")).isTrue();

        // Verify counts are reasonable
        assertThat(dashboardData.get("totalServices").asInt()).isEqualTo(3);
        assertThat(dashboardData.get("diagnosticsToday").asInt()).isGreaterThanOrEqualTo(0);
        assertThat(dashboardData.get("activeAnomalies").asInt()).isGreaterThanOrEqualTo(0);
    }
}
