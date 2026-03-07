package com.foda.rca.fuzzification;

import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.ServiceMetrics;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests that {@link FaultFuzzifierImpl} produces semantically correct fuzzy vectors
 * for canonical metric scenarios used in experimental evaluation (Section 5.2).
 */
@DisplayName("FaultFuzzifierImpl Tests")
class FaultFuzzifierImplTest {

    private FaultFuzzifierImpl fuzzifier;

    @BeforeEach
    void setUp() {
        fuzzifier = new FaultFuzzifierImpl(1000.0); // 1000 req/s baseline
    }

    @Test
    @DisplayName("Healthy service: cpu_LOW and latency_NORMAL dominate")
    void healthyService_lowCpuNormalLatency() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-a").cpuUsage(10).latencyMs(50)
                .memoryUsage(30).errorRate(0.001).throughput(900)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        assertEquals("svc-a", v.getServiceId());
        assertTrue(v.get("cpu_LOW") > 0.9, "Expected cpu_LOW ≈ 1.0");
        assertEquals(0.0, v.get("cpu_HIGH"), 1e-9, "Healthy CPU should not fire cpu_HIGH");
        assertTrue(v.get("latency_NORMAL") > 0.9, "Expected latency_NORMAL ≈ 1.0");
        assertEquals(0.0, v.get("latency_CRITICAL"), 1e-9);
        assertTrue(v.get("errorRate_NONE") > 0.8, "Expected errorRate_NONE ≈ 1.0");
    }

    @Test
    @DisplayName("CPU-saturated service: cpu_HIGH fires, cpu_LOW is zero")
    void cpuSaturatedService() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-b").cpuUsage(92).latencyMs(300)
                .memoryUsage(55).errorRate(0.02).throughput(400)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        assertTrue(v.get("cpu_HIGH") > 0.8, "Expected cpu_HIGH to dominate");
        assertEquals(0.0, v.get("cpu_LOW"), 1e-9);
        assertTrue(v.get("latency_ELEVATED") > 0.0, "Elevated latency expected");
    }

    @Test
    @DisplayName("Critical latency: latency_CRITICAL fires fully")
    void criticalLatency() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-c").cpuUsage(45).latencyMs(800)
                .memoryUsage(60).errorRate(0.005).throughput(700)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        assertTrue(v.get("latency_CRITICAL") > 0.9,
                "P99=800ms should be fully in CRITICAL zone");
        assertEquals(0.0, v.get("latency_NORMAL"), 1e-9);
    }

    @Test
    @DisplayName("High error rate: errorRate_HIGH fires")
    void highErrorRate() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-d").cpuUsage(50).latencyMs(200)
                .memoryUsage(50).errorRate(0.20).throughput(600)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        assertTrue(v.get("errorRate_HIGH") > 0.9, "20% error rate should be fully HIGH");
        assertEquals(0.0, v.get("errorRate_NONE"), 1e-9);
    }

    @Test
    @DisplayName("Low throughput: throughput_LOW fires")
    void lowThroughput() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-e").cpuUsage(80).latencyMs(150)
                .memoryUsage(70).errorRate(0.01).throughput(50)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        assertTrue(v.get("throughput_LOW") > 0.9, "50 req/s should be fully LOW");
        assertEquals(0.0, v.get("throughput_NORMAL"), 1e-9);
    }

    @Test
    @DisplayName("fuzzify rejects null input")
    void nullInput_throws() {
        assertThrows(NullPointerException.class, () -> fuzzifier.fuzzify(null));
    }

    @Test
    @DisplayName("All membership values are in [0, 1]")
    void allMemberships_inUnitInterval() {
        ServiceMetrics m = ServiceMetrics.builder()
                .serviceId("svc-f").cpuUsage(75).latencyMs(350)
                .memoryUsage(85).errorRate(0.08).throughput(300)
                .timestamp("2026-02-22T10:00:00Z").build();

        FuzzyVector v = fuzzifier.fuzzify(m);

        v.getMemberships().forEach((label, mu) ->
            assertTrue(mu >= 0.0 && mu <= 1.0,
                "Membership " + label + "=" + mu + " outside [0,1]"));
    }
}
