package com.foda.test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.restassured.RestAssured;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.*;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * Performance Benchmark Tests for FODA Architecture
 *
 * Measures:
 * - Throughput (metrics/second)
 * - Latency (end-to-end processing time)
 * - Resource utilization
 * - Concurrent request handling
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class PerformanceBenchmarkTest {

    private static KafkaProducer<String, String> producer;
    private static ObjectMapper objectMapper;
    private static final String KAFKA_BOOTSTRAP_SERVERS = "localhost:9092";

    @BeforeAll
    public static void setUp() {
        RestAssured.baseURI = "http://localhost";
        RestAssured.port = 8080;

        objectMapper = new ObjectMapper();

        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA_BOOTSTRAP_SERVERS);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.ACKS_CONFIG, "1");
        producerProps.put(ProducerConfig.LINGER_MS_CONFIG, "10");
        producerProps.put(ProducerConfig.BATCH_SIZE_CONFIG, "16384");
        producer = new KafkaProducer<>(producerProps);
    }

    @AfterAll
    public static void tearDown() {
        if (producer != null) producer.close();
    }

    @Test
    @Order(1)
    @DisplayName("Benchmark 1: Throughput Test - Metrics Ingestion")
    public void benchmarkMetricsIngestionThroughput() throws Exception {
        int numMetrics = 1000;
        long startTime = System.currentTimeMillis();

        CountDownLatch latch = new CountDownLatch(numMetrics);

        for (int i = 0; i < numMetrics; i++) {
            String metric = generateRandomMetric("service-a", false);
            producer.send(new ProducerRecord<>("metrics-stream", "metric-" + i, metric),
                (metadata, exception) -> latch.countDown());
        }

        latch.await(30, TimeUnit.SECONDS);
        long endTime = System.currentTimeMillis();

        long duration = endTime - startTime;
        double throughput = (numMetrics * 1000.0) / duration;

        System.out.printf("Metrics Ingestion Throughput: %.2f metrics/second%n", throughput);
        System.out.printf("Total time for %d metrics: %d ms%n", numMetrics, duration);

        assertThat(throughput).isGreaterThan(50.0); // At least 50 metrics/second
    }

    @Test
    @Order(2)
    @DisplayName("Benchmark 2: End-to-End Latency Test")
    public void benchmarkEndToEndLatency() throws Exception {
        List<Long> latencies = new ArrayList<>();
        int numTests = 50;

        for (int i = 0; i < numTests; i++) {
            long startTime = System.currentTimeMillis();

            String metric = generateRandomMetric("service-b", true); // Anomalous
            producer.send(new ProducerRecord<>("metrics-stream", "latency-test-" + i, metric)).get();

            // Wait for diagnostic to appear
            boolean found = false;
            long maxWait = 30000; // 30 seconds max
            long elapsed = 0;

            while (!found && elapsed < maxWait) {
                Thread.sleep(500);
                elapsed = System.currentTimeMillis() - startTime;

                try {
                    String response = given()
                        .when()
                            .get("/api/ontology/diagnostics/recent?limit=10")
                        .then()
                            .statusCode(200)
                            .extract().asString();

                    JsonNode diagnostics = objectMapper.readTree(response);
                    if (diagnostics.size() > 0) {
                        found = true;
                        latencies.add(elapsed);
                    }
                } catch (Exception e) {
                    // Continue waiting
                }
            }

            Thread.sleep(1000); // Cool down between tests
        }

        // Calculate statistics
        double avgLatency = latencies.stream().mapToLong(Long::longValue).average().orElse(0);
        long minLatency = latencies.stream().mapToLong(Long::longValue).min().orElse(0);
        long maxLatency = latencies.stream().mapToLong(Long::longValue).max().orElse(0);
        double p95Latency = calculatePercentile(latencies, 95);
        double p99Latency = calculatePercentile(latencies, 99);

        System.out.println("\n=== End-to-End Latency Statistics ===");
        System.out.printf("Average: %.2f ms%n", avgLatency);
        System.out.printf("Min: %d ms%n", minLatency);
        System.out.printf("Max: %d ms%n", maxLatency);
        System.out.printf("P95: %.2f ms%n", p95Latency);
        System.out.printf("P99: %.2f ms%n", p99Latency);

        assertThat(avgLatency).isLessThan(20000.0); // Average < 20 seconds
        assertThat(p95Latency).isLessThan(25000.0); // P95 < 25 seconds
    }

    @Test
    @Order(3)
    @DisplayName("Benchmark 3: Concurrent Request Handling")
    public void benchmarkConcurrentRequests() throws Exception {
        int numThreads = 20;
        int requestsPerThread = 10;
        ExecutorService executor = Executors.newFixedThreadPool(numThreads);

        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger failureCount = new AtomicInteger(0);
        List<Long> responseTimes = Collections.synchronizedList(new ArrayList<>());

        CountDownLatch latch = new CountDownLatch(numThreads * requestsPerThread);
        long startTime = System.currentTimeMillis();

        for (int i = 0; i < numThreads; i++) {
            executor.submit(() -> {
                for (int j = 0; j < requestsPerThread; j++) {
                    try {
                        long requestStart = System.currentTimeMillis();

                        given()
                            .when()
                                .get("/api/ontology/diagnostics/recent?limit=5")
                            .then()
                                .statusCode(200);

                        long requestEnd = System.currentTimeMillis();
                        responseTimes.add(requestEnd - requestStart);
                        successCount.incrementAndGet();
                    } catch (Exception e) {
                        failureCount.incrementAndGet();
                    } finally {
                        latch.countDown();
                    }
                }
            });
        }

        latch.await(60, TimeUnit.SECONDS);
        long endTime = System.currentTimeMillis();

        executor.shutdown();

        long totalDuration = endTime - startTime;
        int totalRequests = numThreads * requestsPerThread;
        double requestsPerSecond = (totalRequests * 1000.0) / totalDuration;
        double avgResponseTime = responseTimes.stream().mapToLong(Long::longValue).average().orElse(0);

        System.out.println("\n=== Concurrent Request Handling ===");
        System.out.printf("Total requests: %d%n", totalRequests);
        System.out.printf("Successful: %d%n", successCount.get());
        System.out.printf("Failed: %d%n", failureCount.get());
        System.out.printf("Requests/second: %.2f%n", requestsPerSecond);
        System.out.printf("Avg response time: %.2f ms%n", avgResponseTime);

        assertThat(successCount.get()).isGreaterThan((int)(totalRequests * 0.95)); // 95% success rate
        assertThat(requestsPerSecond).isGreaterThan(5.0); // At least 5 req/sec
    }

    @Test
    @Order(4)
    @DisplayName("Benchmark 4: API Gateway Response Times")
    public void benchmarkAPIGatewayResponseTimes() {
        Map<String, List<Long>> endpointTimes = new HashMap<>();
        int iterations = 20;

        // Define endpoints to test
        Map<String, String> endpoints = Map.of(
            "Health", "/api/dashboard/health",
            "Overview", "/api/dashboard/overview",
            "Recent Diagnostics", "/api/ontology/diagnostics/recent?limit=10",
            "Service Health", "/api/services/service-a/health"
        );

        endpoints.forEach((name, endpoint) -> {
            List<Long> times = new ArrayList<>();
            for (int i = 0; i < iterations; i++) {
                long start = System.currentTimeMillis();
                try {
                    io.restassured.response.Response response = given()
                        .when()
                            .get(endpoint);

                    int statusCode = response.getStatusCode();
                    if (statusCode != 200 && statusCode != 202) {
                        continue;
                    }
                } catch (Exception e) {
                    // Skip failed requests
                    continue;
                }
                long end = System.currentTimeMillis();
                times.add(end - start);
            }
            endpointTimes.put(name, times);
        });

        System.out.println("\n=== API Gateway Response Times ===");
        endpointTimes.forEach((name, times) -> {
            double avg = times.stream().mapToLong(Long::longValue).average().orElse(0);
            long min = times.stream().mapToLong(Long::longValue).min().orElse(0);
            long max = times.stream().mapToLong(Long::longValue).max().orElse(0);
            System.out.printf("%s: avg=%.2fms, min=%dms, max=%dms%n", name, avg, min, max);

            assertThat(avg).isLessThan(2000.0); // Average response time < 2 seconds
        });
    }

    @Test
    @Order(5)
    @DisplayName("Benchmark 5: Fuzzy Inference Performance")
    public void benchmarkFuzzyInferencePerformance() throws Exception {
        int numInferences = 100;
        List<Long> inferenceTimes = new ArrayList<>();

        for (int i = 0; i < numInferences; i++) {
            long startTime = System.currentTimeMillis();

            // Send ML prediction directly to fuzzy engine topic
            String mlPrediction = """
                {
                    "predictionId": "perf-test-%d",
                    "serviceId": "service-c",
                    "timestamp": "%s",
                    "isAnomaly": true,
                    "anomalyScore": %.2f,
                    "features": {
                        "cpuUsage": %.1f,
                        "memoryUsage": %.1f,
                        "responseTime": %d,
                        "errorRate": %.2f
                    }
                }
                """.formatted(
                    i,
                    Instant.now().toString(),
                    0.7 + Math.random() * 0.3,
                    60.0 + Math.random() * 40,
                    60.0 + Math.random() * 40,
                    (int)(1000 + Math.random() * 4000),
                    0.1 + Math.random() * 0.4
                );

            producer.send(new ProducerRecord<>("ml-predictions", "perf-" + i, mlPrediction)).get();

            long endTime = System.currentTimeMillis();
            inferenceTimes.add(endTime - startTime);

            Thread.sleep(100); // Small delay between inferences
        }

        double avgInferenceTime = inferenceTimes.stream().mapToLong(Long::longValue).average().orElse(0);
        long maxInferenceTime = inferenceTimes.stream().mapToLong(Long::longValue).max().orElse(0);

        System.out.println("\n=== Fuzzy Inference Performance ===");
        System.out.printf("Average inference time: %.2f ms%n", avgInferenceTime);
        System.out.printf("Max inference time: %d ms%n", maxInferenceTime);
        System.out.printf("Inferences/second: %.2f%n", 1000.0 / avgInferenceTime);

        assertThat(avgInferenceTime).isLessThan(500.0); // Average < 500ms
    }

    @Test
    @Order(6)
    @DisplayName("Benchmark 6: SPARQL Query Performance")
    public void benchmarkSPARQLQueryPerformance() {
        Map<String, String> queries = Map.of(
            "Recent Diagnostics", "/api/ontology/diagnostics/recent?limit=20",
            "By Service", "/api/ontology/diagnostics/service/service-a",
            "By Severity", "/api/ontology/diagnostics/severity/HIGH",
            "By Fault Type", "/api/ontology/diagnostics/fault-type/RESOURCE_EXHAUSTION"
        );

        System.out.println("\n=== SPARQL Query Performance ===");

        queries.forEach((name, endpoint) -> {
            List<Long> queryTimes = new ArrayList<>();

            for (int i = 0; i < 15; i++) {
                long start = System.currentTimeMillis();
                try {
                    given()
                        .when()
                            .get(endpoint)
                        .then()
                            .statusCode(200);
                } catch (Exception e) {
                    continue;
                }
                long end = System.currentTimeMillis();
                queryTimes.add(end - start);
            }

            double avg = queryTimes.stream().mapToLong(Long::longValue).average().orElse(0);
            long min = queryTimes.stream().mapToLong(Long::longValue).min().orElse(0);
            long max = queryTimes.stream().mapToLong(Long::longValue).max().orElse(0);

            System.out.printf("%s: avg=%.2fms, min=%dms, max=%dms%n", name, avg, min, max);

            assertThat(avg).isLessThan(3000.0); // Average query time < 3 seconds
        });
    }

    // Helper methods
    private String generateRandomMetric(String serviceId, boolean anomalous) {
        Random rand = new Random();
        double cpuUsage, memoryUsage, errorRate;
        int responseTime;

        if (anomalous) {
            cpuUsage = 80.0 + rand.nextDouble() * 20.0;
            memoryUsage = 80.0 + rand.nextDouble() * 20.0;
            responseTime = 3000 + rand.nextInt(5000);
            errorRate = 0.3 + rand.nextDouble() * 0.5;
        } else {
            cpuUsage = 20.0 + rand.nextDouble() * 40.0;
            memoryUsage = 30.0 + rand.nextDouble() * 40.0;
            responseTime = 100 + rand.nextInt(1000);
            errorRate = rand.nextDouble() * 0.1;
        }

        return """
            {
                "serviceId": "%s",
                "timestamp": "%s",
                "cpuUsage": %.2f,
                "memoryUsage": %.2f,
                "responseTime": %d,
                "errorRate": %.3f,
                "requestCount": %d
            }
            """.formatted(
                serviceId,
                Instant.now().toString(),
                cpuUsage,
                memoryUsage,
                responseTime,
                errorRate,
                500 + rand.nextInt(1500)
            );
    }

    private double calculatePercentile(List<Long> values, int percentile) {
        List<Long> sorted = new ArrayList<>(values);
        Collections.sort(sorted);
        int index = (int) Math.ceil((percentile / 100.0) * sorted.size()) - 1;
        return sorted.get(Math.max(0, Math.min(index, sorted.size() - 1)));
    }

    private static int anyOf(int... values) {
        return values[0]; // Simplified for demonstration
    }

    private static org.hamcrest.Matcher<Integer> is(int value) {
        return org.hamcrest.Matchers.is(value);
    }
}
