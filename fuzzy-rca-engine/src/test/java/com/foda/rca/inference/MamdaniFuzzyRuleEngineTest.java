package com.foda.rca.inference;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link MamdaniFuzzyRuleEngine}.
 * Verifies that the Mamdani firing mechanism correctly identifies fault categories
 * from representative fuzzy vectors.
 */
@DisplayName("MamdaniFuzzyRuleEngine Tests")
class MamdaniFuzzyRuleEngineTest {

    private MamdaniFuzzyRuleEngine engine;

    @BeforeEach
    void setUp() {
        engine = new MamdaniFuzzyRuleEngine();
    }

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    private FuzzyVector vector(String serviceId, Map<String, Double> memberships) {
        return FuzzyVector.builder().serviceId(serviceId).memberships(memberships).build();
    }

    // -----------------------------------------------------------------------
    // Rule-firing tests
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Clear CPU saturation pattern → CPU_SATURATION dominates")
    void cpuSaturation_dominates() {
        FuzzyVector v = vector("svc-a", Map.of(
                "cpu_HIGH",        0.90,
                "latency_ELEVATED",0.75,
                "throughput_LOW",  0.80,
                "errorRate_NONE",  0.50
        ));

        FaultHypothesis h = engine.infer(v);

        assertEquals("CPU_SATURATION", h.getDominantFaultCategory());
        assertTrue(h.getLocalConfidence() > 0.5,
                "Confidence should be elevated for clear CPU saturation pattern");
        assertFalse(h.getFiredRules().isEmpty(), "Some rules should have fired");
    }

    @Test
    @DisplayName("High error rate → SERVICE_ERROR dominates")
    void highErrorRate_serviceError() {
        FuzzyVector v = vector("svc-b", Map.of(
                "errorRate_HIGH",  0.95,
                "cpu_MEDIUM",      0.40,
                "latency_NORMAL",  0.60
        ));

        FaultHypothesis h = engine.infer(v);

        assertEquals("SERVICE_ERROR", h.getDominantFaultCategory());
        // R07 has CF=0.90 and errorRate_HIGH=0.95 → α = 0.90 * 0.95 = 0.855
        assertTrue(h.getLocalConfidence() > 0.80,
                "H should reflect high error rate confidence");
    }

    @Test
    @DisplayName("Critical latency alone → LATENCY_ANOMALY")
    void criticalLatency_latencyAnomaly() {
        FuzzyVector v = vector("svc-c", Map.of(
                "latency_CRITICAL", 1.0,
                "cpu_LOW",         0.90,
                "errorRate_NONE",  0.80
        ));

        FaultHypothesis h = engine.infer(v);

        assertEquals("LATENCY_ANOMALY", h.getDominantFaultCategory());
        // R10: CF=0.88, μ=1.0 → α=0.88
        assertEquals(0.88, h.getLocalConfidence(), 0.01);
    }

    @Test
    @DisplayName("Combined high CPU + high memory + critical latency → CASCADING_FAILURE")
    void cascadingFailure() {
        FuzzyVector v = vector("svc-d", Map.of(
                "cpu_HIGH",        1.00,
                "memory_HIGH",     0.95,
                "latency_CRITICAL",0.90,
                "errorRate_ELEVATED", 0.70
        ));

        FaultHypothesis h = engine.infer(v);

        assertEquals("CASCADING_FAILURE", h.getDominantFaultCategory());
        assertTrue(h.getLocalConfidence() > 0.80,
                "Multi-resource + latency failure should have very high confidence");
    }

    @Test
    @DisplayName("Healthy service metrics → no FAULT rules fire → H=0 (UNKNOWN/no-fault)")
    void healthyService_noFaultRulesFire() {
        FuzzyVector v = vector("svc-e", Map.of(
                "cpu_LOW",          0.95,
                "memory_LOW",       0.90,
                "latency_NORMAL",   0.92,
                "errorRate_NONE",   0.98,
                "throughput_NORMAL",0.88
        ));

        FaultHypothesis h = engine.infer(v);

        // A healthy service has no FAULT patterns → no rules fire → H = 0
        assertEquals(0.0, h.getLocalConfidence(), 1e-9,
                "Healthy service should produce H=0 (no fault evidence)");
        assertEquals("UNKNOWN", h.getDominantFaultCategory());
        assertTrue(h.getFiredRules().isEmpty(), "No fault rules should fire for healthy service");
    }

    @Test
    @DisplayName("Zero fuzzy memberships → no rules fire → UNKNOWN with H=0")
    void zeroMemberships_noRulesFire() {
        FuzzyVector v = vector("svc-f", Map.of());

        FaultHypothesis h = engine.infer(v);

        assertEquals(0.0, h.getLocalConfidence(), 1e-9);
        assertEquals("UNKNOWN", h.getDominantFaultCategory());
        assertTrue(h.getFiredRules().isEmpty());
    }

    @Test
    @DisplayName("Local confidence H is always in [0, 1]")
    void localConfidence_inUnitInterval() {
        FuzzyVector v = vector("svc-g", Map.of(
                "cpu_HIGH", 0.99, "memory_HIGH", 0.99,
                "latency_CRITICAL", 0.99, "errorRate_HIGH", 0.99,
                "throughput_LOW", 0.99
        ));
        FaultHypothesis h = engine.infer(v);
        assertTrue(h.getLocalConfidence() >= 0.0 && h.getLocalConfidence() <= 1.0,
                "H must be in [0, 1]");
    }

    @Test
    @DisplayName("Memory high + throughput low → MEMORY_PRESSURE")
    void memoryPressure() {
        FuzzyVector v = vector("svc-h", Map.of(
                "memory_HIGH",     0.92,
                "throughput_LOW",  0.85,
                "cpu_MEDIUM",      0.60,
                "latency_ELEVATED",0.50
        ));
        FaultHypothesis h = engine.infer(v);
        assertEquals("MEMORY_PRESSURE", h.getDominantFaultCategory());
    }

    @Test
    @DisplayName("Rule base is non-empty")
    void defaultRuleBase_nonEmpty() {
        assertTrue(engine.getRuleBase().size() >= 15,
                "Default rule base should contain at least 15 rules");
    }
}
