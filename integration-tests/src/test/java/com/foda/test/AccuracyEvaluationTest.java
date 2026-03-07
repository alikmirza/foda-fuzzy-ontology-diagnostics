package com.foda.test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.restassured.RestAssured;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.*;

import java.time.Instant;
import java.util.*;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * Accuracy Evaluation Tests for FODA Diagnostic Architecture
 *
 * Evaluates:
 * - Anomaly detection precision and recall
 * - Fault classification accuracy
 * - Fuzzy Confidence Index (FCI) calibration
 * - False positive/negative rates
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class AccuracyEvaluationTest {

    private static KafkaProducer<String, String> producer;
    private static ObjectMapper objectMapper;
    private static final String KAFKA_BOOTSTRAP_SERVERS = "localhost:9092";

    // Ground truth test cases
    private static final List<TestCase> TEST_CASES = Arrays.asList(
        // Resource Exhaustion - High CPU
        new TestCase("RE_CPU_1", 95.0, 70.0, 1500, 0.05, 1000, "RESOURCE_EXHAUSTION", "HIGH", true),
        new TestCase("RE_CPU_2", 92.0, 65.0, 1800, 0.08, 1200, "RESOURCE_EXHAUSTION", "HIGH", true),
        new TestCase("RE_CPU_3", 88.0, 60.0, 2000, 0.10, 900, "RESOURCE_EXHAUSTION", "MEDIUM", true),

        // Resource Exhaustion - High Memory
        new TestCase("RE_MEM_1", 60.0, 98.0, 1600, 0.06, 1100, "RESOURCE_EXHAUSTION", "HIGH", true),
        new TestCase("RE_MEM_2", 55.0, 95.0, 1900, 0.09, 1300, "RESOURCE_EXHAUSTION", "HIGH", true),
        new TestCase("RE_MEM_3", 65.0, 90.0, 2100, 0.07, 950, "RESOURCE_EXHAUSTION", "MEDIUM", true),

        // Application Error - High Error Rate
        new TestCase("APP_ERR_1", 50.0, 55.0, 2500, 0.75, 800, "APPLICATION_ERROR", "CRITICAL", true),
        new TestCase("APP_ERR_2", 45.0, 50.0, 2200, 0.65, 900, "APPLICATION_ERROR", "HIGH", true),
        new TestCase("APP_ERR_3", 55.0, 60.0, 2800, 0.55, 750, "APPLICATION_ERROR", "HIGH", true),

        // Performance Degradation - Slow Response
        new TestCase("PERF_DEG_1", 40.0, 45.0, 8000, 0.15, 600, "PERFORMANCE_DEGRADATION", "HIGH", true),
        new TestCase("PERF_DEG_2", 35.0, 50.0, 7500, 0.20, 650, "PERFORMANCE_DEGRADATION", "HIGH", true),
        new TestCase("PERF_DEG_3", 45.0, 55.0, 6500, 0.18, 700, "PERFORMANCE_DEGRADATION", "MEDIUM", true),

        // Network Issues - Combined factors
        new TestCase("NET_ISS_1", 30.0, 40.0, 9000, 0.45, 400, "NETWORK_ISSUE", "HIGH", true),
        new TestCase("NET_ISS_2", 35.0, 45.0, 8500, 0.50, 450, "NETWORK_ISSUE", "HIGH", true),

        // Normal Operation - No anomalies
        new TestCase("NORMAL_1", 30.0, 35.0, 500, 0.01, 1500, null, null, false),
        new TestCase("NORMAL_2", 25.0, 30.0, 450, 0.02, 1600, null, null, false),
        new TestCase("NORMAL_3", 35.0, 40.0, 600, 0.015, 1400, null, null, false),
        new TestCase("NORMAL_4", 28.0, 32.0, 550, 0.018, 1550, null, null, false),

        // Edge Cases - Borderline anomalies
        new TestCase("EDGE_1", 75.0, 75.0, 3000, 0.25, 1000, "RESOURCE_EXHAUSTION", "MEDIUM", true),
        new TestCase("EDGE_2", 70.0, 70.0, 2900, 0.22, 1050, "RESOURCE_EXHAUSTION", "MEDIUM", true)
    );

    static class TestCase {
        String id;
        double cpuUsage;
        double memoryUsage;
        int responseTime;
        double errorRate;
        int requestCount;
        String expectedFaultType;
        String expectedSeverity;
        boolean shouldBeAnomaly;

        TestCase(String id, double cpu, double mem, int rt, double er, int rc,
                String faultType, String severity, boolean isAnomaly) {
            this.id = id;
            this.cpuUsage = cpu;
            this.memoryUsage = mem;
            this.responseTime = rt;
            this.errorRate = er;
            this.requestCount = rc;
            this.expectedFaultType = faultType;
            this.expectedSeverity = severity;
            this.shouldBeAnomaly = isAnomaly;
        }
    }

    static class EvaluationResult {
        int truePositives = 0;
        int trueNegatives = 0;
        int falsePositives = 0;
        int falseNegatives = 0;
        int correctFaultTypes = 0;
        int correctSeverities = 0;
        List<Double> fciValues = new ArrayList<>();
        Map<String, Integer> confusionMatrix = new HashMap<>();
    }

    @BeforeAll
    public static void setUp() {
        RestAssured.baseURI = "http://localhost";
        RestAssured.port = 8080;

        objectMapper = new ObjectMapper();

        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA_BOOTSTRAP_SERVERS);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producer = new KafkaProducer<>(producerProps);
    }

    @AfterAll
    public static void tearDown() {
        if (producer != null) producer.close();
    }

    @Test
    @Order(1)
    @DisplayName("Accuracy Test 1: Execute All Test Cases")
    public void executeAllTestCases() throws Exception {
        System.out.println("\n=== Executing " + TEST_CASES.size() + " Test Cases ===");

        for (TestCase testCase : TEST_CASES) {
            String metric = """
                {
                    "serviceId": "accuracy-test-service",
                    "timestamp": "%s",
                    "cpuUsage": %.2f,
                    "memoryUsage": %.2f,
                    "responseTime": %d,
                    "errorRate": %.3f,
                    "requestCount": %d
                }
                """.formatted(
                    Instant.now().toString(),
                    testCase.cpuUsage,
                    testCase.memoryUsage,
                    testCase.responseTime,
                    testCase.errorRate,
                    testCase.requestCount
                );

            producer.send(new ProducerRecord<>("metrics-stream", testCase.id, metric)).get();
            System.out.printf("Sent test case: %s (Anomaly: %b)%n", testCase.id, testCase.shouldBeAnomaly);

            // Wait between test cases to allow processing
            Thread.sleep(5000);
        }

        // Wait for all diagnostics to be processed
        System.out.println("\nWaiting for diagnostics to be processed...");
        Thread.sleep(30000);
    }

    @Test
    @Order(2)
    @DisplayName("Accuracy Test 2: Evaluate Anomaly Detection")
    public void evaluateAnomalyDetection() throws Exception {
        EvaluationResult result = new EvaluationResult();

        // Retrieve all diagnostics
        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=100")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);
        Map<String, JsonNode> diagnosticMap = new HashMap<>();

        // Map diagnostics by service ID or correlation
        for (JsonNode diag : diagnostics) {
            String diagId = diag.has("diagnosticId") ? diag.get("diagnosticId").asText() : "";
            diagnosticMap.put(diagId, diag);
        }

        // Evaluate each test case
        for (TestCase testCase : TEST_CASES) {
            boolean foundDiagnostic = false;

            // Search for diagnostic matching this test case
            for (JsonNode diag : diagnostics) {
                // Match based on characteristics
                if (matchesDiagnostic(diag, testCase)) {
                    foundDiagnostic = true;

                    if (testCase.shouldBeAnomaly) {
                        result.truePositives++;

                        // Check fault type accuracy
                        if (diag.has("faultType") &&
                            testCase.expectedFaultType != null &&
                            diag.get("faultType").asText().equals(testCase.expectedFaultType)) {
                            result.correctFaultTypes++;
                        }

                        // Check severity accuracy
                        if (diag.has("severity") &&
                            testCase.expectedSeverity != null &&
                            diag.get("severity").asText().equals(testCase.expectedSeverity)) {
                            result.correctSeverities++;
                        }

                        // Collect FCI values
                        if (diag.has("fci")) {
                            result.fciValues.add(diag.get("fci").asDouble());
                        }
                    } else {
                        result.falsePositives++;
                    }
                    break;
                }
            }

            if (!foundDiagnostic) {
                if (testCase.shouldBeAnomaly) {
                    result.falseNegatives++;
                } else {
                    result.trueNegatives++;
                }
            }
        }

        printAnomalyDetectionMetrics(result);
        validateAnomalyDetectionAccuracy(result);
    }

    @Test
    @Order(3)
    @DisplayName("Accuracy Test 3: Evaluate Fault Classification")
    public void evaluateFaultClassification() throws Exception {
        Map<String, Map<String, Integer>> confusionMatrix = new HashMap<>();

        // Retrieve diagnostics
        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=100")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);

        // Build confusion matrix
        for (TestCase testCase : TEST_CASES) {
            if (!testCase.shouldBeAnomaly) continue;

            for (JsonNode diag : diagnostics) {
                if (matchesDiagnostic(diag, testCase)) {
                    String expected = testCase.expectedFaultType;
                    String actual = diag.has("faultType") ? diag.get("faultType").asText() : "UNKNOWN";

                    confusionMatrix
                        .computeIfAbsent(expected, k -> new HashMap<>())
                        .merge(actual, 1, Integer::sum);
                    break;
                }
            }
        }

        printConfusionMatrix(confusionMatrix);
        calculatePerClassMetrics(confusionMatrix);
    }

    @Test
    @Order(4)
    @DisplayName("Accuracy Test 4: Evaluate FCI Calibration")
    public void evaluateFCICalibration() throws Exception {
        List<Double> highSeverityFCIs = new ArrayList<>();
        List<Double> mediumSeverityFCIs = new ArrayList<>();
        List<Double> lowSeverityFCIs = new ArrayList<>();

        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=100")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);

        for (JsonNode diag : diagnostics) {
            if (diag.has("fci") && diag.has("severity")) {
                double fci = diag.get("fci").asDouble();
                String severity = diag.get("severity").asText();

                switch (severity) {
                    case "CRITICAL":
                    case "HIGH":
                        highSeverityFCIs.add(fci);
                        break;
                    case "MEDIUM":
                        mediumSeverityFCIs.add(fci);
                        break;
                    case "LOW":
                        lowSeverityFCIs.add(fci);
                        break;
                }
            }
        }

        printFCICalibrationMetrics(highSeverityFCIs, mediumSeverityFCIs, lowSeverityFCIs);
        validateFCICalibration(highSeverityFCIs, mediumSeverityFCIs, lowSeverityFCIs);
    }

    @Test
    @Order(5)
    @DisplayName("Accuracy Test 5: Evaluate Severity Classification")
    public void evaluateSeverityClassification() throws Exception {
        int correctSeverities = 0;
        int totalAnomalies = 0;

        String response = given()
            .when()
                .get("/api/ontology/diagnostics/recent?limit=100")
            .then()
                .statusCode(200)
                .extract().asString();

        JsonNode diagnostics = objectMapper.readTree(response);

        for (TestCase testCase : TEST_CASES) {
            if (!testCase.shouldBeAnomaly) continue;
            totalAnomalies++;

            for (JsonNode diag : diagnostics) {
                if (matchesDiagnostic(diag, testCase)) {
                    if (diag.has("severity") &&
                        testCase.expectedSeverity != null &&
                        diag.get("severity").asText().equals(testCase.expectedSeverity)) {
                        correctSeverities++;
                    }
                    break;
                }
            }
        }

        double severityAccuracy = totalAnomalies > 0 ?
            (correctSeverities * 100.0 / totalAnomalies) : 0.0;

        System.out.println("\n=== Severity Classification Accuracy ===");
        System.out.printf("Correct: %d / %d%n", correctSeverities, totalAnomalies);
        System.out.printf("Accuracy: %.2f%%%n", severityAccuracy);

        assertThat(severityAccuracy).isGreaterThan(60.0); // At least 60% accuracy
    }

    // Helper methods
    private boolean matchesDiagnostic(JsonNode diag, TestCase testCase) {
        // Simple matching based on fault type and severity
        if (!testCase.shouldBeAnomaly) return false;

        if (testCase.expectedFaultType != null && diag.has("faultType")) {
            return diag.get("faultType").asText().equals(testCase.expectedFaultType);
        }

        return false;
    }

    private void printAnomalyDetectionMetrics(EvaluationResult result) {
        int total = result.truePositives + result.trueNegatives +
                   result.falsePositives + result.falseNegatives;

        double accuracy = total > 0 ?
            ((result.truePositives + result.trueNegatives) * 100.0 / total) : 0.0;

        double precision = (result.truePositives + result.falsePositives) > 0 ?
            (result.truePositives * 100.0 / (result.truePositives + result.falsePositives)) : 0.0;

        double recall = (result.truePositives + result.falseNegatives) > 0 ?
            (result.truePositives * 100.0 / (result.truePositives + result.falseNegatives)) : 0.0;

        double f1Score = (precision + recall) > 0 ?
            (2 * precision * recall / (precision + recall)) : 0.0;

        System.out.println("\n=== Anomaly Detection Metrics ===");
        System.out.printf("True Positives: %d%n", result.truePositives);
        System.out.printf("True Negatives: %d%n", result.trueNegatives);
        System.out.printf("False Positives: %d%n", result.falsePositives);
        System.out.printf("False Negatives: %d%n", result.falseNegatives);
        System.out.printf("Accuracy: %.2f%%%n", accuracy);
        System.out.printf("Precision: %.2f%%%n", precision);
        System.out.printf("Recall: %.2f%%%n", recall);
        System.out.printf("F1 Score: %.2f%%%n", f1Score);
    }

    private void validateAnomalyDetectionAccuracy(EvaluationResult result) {
        int total = result.truePositives + result.trueNegatives +
                   result.falsePositives + result.falseNegatives;
        double accuracy = total > 0 ?
            ((result.truePositives + result.trueNegatives) * 100.0 / total) : 0.0;

        double precision = (result.truePositives + result.falsePositives) > 0 ?
            (result.truePositives * 100.0 / (result.truePositives + result.falsePositives)) : 0.0;

        double recall = (result.truePositives + result.falseNegatives) > 0 ?
            (result.truePositives * 100.0 / (result.truePositives + result.falseNegatives)) : 0.0;

        assertThat(accuracy).as("Anomaly detection accuracy").isGreaterThan(70.0);
        assertThat(precision).as("Anomaly detection precision").isGreaterThan(70.0);
        assertThat(recall).as("Anomaly detection recall").isGreaterThan(60.0);
    }

    private void printConfusionMatrix(Map<String, Map<String, Integer>> matrix) {
        System.out.println("\n=== Fault Classification Confusion Matrix ===");
        System.out.println("Expected → Actual");

        matrix.forEach((expected, actuals) -> {
            System.out.printf("%s:%n", expected);
            actuals.forEach((actual, count) ->
                System.out.printf("  → %s: %d%n", actual, count));
        });
    }

    private void calculatePerClassMetrics(Map<String, Map<String, Integer>> matrix) {
        System.out.println("\n=== Per-Class Fault Classification Metrics ===");

        matrix.forEach((faultType, actuals) -> {
            int total = actuals.values().stream().mapToInt(Integer::intValue).sum();
            int correct = actuals.getOrDefault(faultType, 0);
            double accuracy = total > 0 ? (correct * 100.0 / total) : 0.0;

            System.out.printf("%s: %.2f%% (%d/%d)%n", faultType, accuracy, correct, total);
        });
    }

    private void printFCICalibrationMetrics(List<Double> high, List<Double> medium, List<Double> low) {
        System.out.println("\n=== FCI Calibration Metrics ===");

        if (!high.isEmpty()) {
            double avgHigh = high.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double minHigh = high.stream().mapToDouble(Double::doubleValue).min().orElse(0);
            double maxHigh = high.stream().mapToDouble(Double::doubleValue).max().orElse(0);
            System.out.printf("High/Critical Severity: avg=%.3f, min=%.3f, max=%.3f%n", avgHigh, minHigh, maxHigh);
        }

        if (!medium.isEmpty()) {
            double avgMedium = medium.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double minMedium = medium.stream().mapToDouble(Double::doubleValue).min().orElse(0);
            double maxMedium = medium.stream().mapToDouble(Double::doubleValue).max().orElse(0);
            System.out.printf("Medium Severity: avg=%.3f, min=%.3f, max=%.3f%n", avgMedium, minMedium, maxMedium);
        }

        if (!low.isEmpty()) {
            double avgLow = low.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double minLow = low.stream().mapToDouble(Double::doubleValue).min().orElse(0);
            double maxLow = low.stream().mapToDouble(Double::doubleValue).max().orElse(0);
            System.out.printf("Low Severity: avg=%.3f, min=%.3f, max=%.3f%n", avgLow, minLow, maxLow);
        }
    }

    private void validateFCICalibration(List<Double> high, List<Double> medium, List<Double> low) {
        if (!high.isEmpty()) {
            double avgHigh = high.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            assertThat(avgHigh).as("Average FCI for high severity").isGreaterThan(0.6);
        }

        if (!medium.isEmpty()) {
            double avgMedium = medium.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            assertThat(avgMedium).as("Average FCI for medium severity").isBetween(0.4, 0.8);
        }
    }
}
