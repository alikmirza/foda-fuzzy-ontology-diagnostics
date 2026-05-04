package com.foda.rca.explanation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.RankedCause;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.ThrowingSupplier;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link OntologyGroundedExplanationBuilder}.
 *
 * <p>These tests validate the integration between the FCP-RCA fault categories and the
 * populated {@code DiagnosticKB.owl} ontology: vocabulary mapping, IRI rendering,
 * recommendation lookup, six-paragraph structure, and graceful fallback for unmapped
 * categories.</p>
 */
@DisplayName("OntologyGroundedExplanationBuilder")
class OntologyGroundedExplanationBuilderTest {

    private static OntologyGroundedExplanationBuilder builder;

    @BeforeAll
    static void loadBuilder() {
        builder = new OntologyGroundedExplanationBuilder();
    }

    // ---------------------------------------------------------------------
    // Construction / loading
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("Builder instantiates without errors and pre-caches all six categories")
    void instantiates_withCachedEnrichments() {
        // Cast disambiguates between the Executable and ThrowingSupplier overloads
        // of assertDoesNotThrow when the lambda's reference is a no-arg constructor.
        ThrowingSupplier<OntologyGroundedExplanationBuilder> ctor =
                OntologyGroundedExplanationBuilder::new;
        OntologyGroundedExplanationBuilder fresh = assertDoesNotThrow(ctor);

        Map<String, OntologyGroundedExplanationBuilder.OntologyEnrichment> enrichments =
                fresh.enrichmentByCategory();

        assertEquals(6, enrichments.size(),
                "Expected 6 cached enrichments (one per mapped fault category)");
        assertAll("each cached enrichment must carry a label and recommendation",
                enrichments.entrySet().stream().map(e -> () -> {
                    assertNotNull(e.getValue().label(),
                            "label must be non-null for " + e.getKey());
                    assertFalse(e.getValue().label().isBlank(),
                            "label must be non-blank for " + e.getKey());
                    assertNotNull(e.getValue().recommendation(),
                            "recommendation must be non-null for " + e.getKey());
                }));
    }

    // ---------------------------------------------------------------------
    // explain() output for each mapped category
    // ---------------------------------------------------------------------

    @ParameterizedTest(name = "explain() returns non-blank text for category {0}")
    @ValueSource(strings = {
            "CPU_SATURATION",
            "LATENCY_ANOMALY",
            "MEMORY_PRESSURE",
            "SERVICE_ERROR",
            "RESOURCE_CONTENTION",
            "CASCADING_FAILURE"
    })
    void explain_nonBlank_perCategory(String category) {
        String out = builder.explain(
                rankedCause("svc-x", category),
                vector("svc-x"),
                hypothesis("svc-x", category));
        assertNotNull(out, "explain() must not return null for " + category);
        assertFalse(out.isBlank(), "explain() must not return blank for " + category);
        assertTrue(out.contains("svc-x"),
                "explanation must mention the service id for " + category);
    }

    // ---------------------------------------------------------------------
    // Ontology IRI is included
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("LATENCY_ANOMALY explanation contains diagnostic:LatencySpike IRI")
    void latencyAnomaly_includesOntologyIri() {
        String out = builder.explain(
                rankedCause("payment-svc", "LATENCY_ANOMALY"),
                vector("payment-svc"),
                hypothesis("payment-svc", "LATENCY_ANOMALY"));
        assertTrue(out.contains("diagnostic:LatencySpike"),
                "expected output to contain 'diagnostic:LatencySpike'; was:\n" + out);
    }

    // ---------------------------------------------------------------------
    // Recommended action comes from the ontology, not the hard-coded switch
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("CPU_SATURATION uses ontology recommendation in 'Recommended action' paragraph")
    void cpuSaturation_recommendedAction_fromOntology() {
        String out = builder.explain(
                rankedCause("api-gw", "CPU_SATURATION"),
                vector("api-gw"),
                hypothesis("api-gw", "CPU_SATURATION"));

        // Substring is taken from Rec_CpuSaturation.description in DiagnosticKB.owl;
        // proves the ontology was consulted, not the legacy hard-coded switch.
        assertTrue(out.contains("Scale out CPU-bound services horizontally"),
                "expected ontology recommendation text in output; was:\n" + out);
        assertFalse(out.contains("optimise CPU-intensive code paths"),
                "must not contain the legacy NaturalLanguageExplanationBuilder phrasing; was:\n" + out);
    }

    // ---------------------------------------------------------------------
    // Six-paragraph structure
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("Output has 6 paragraphs (legacy is 5; we added Contributing factors)")
    void sixParagraphStructure() {
        String out = builder.explain(
                rankedCause("db-svc", "MEMORY_PRESSURE"),
                vector("db-svc"),
                hypothesis("db-svc", "MEMORY_PRESSURE"));

        String[] paragraphs = out.split("\n\n");
        assertEquals(6, paragraphs.length,
                "expected 6 paragraphs separated by blank lines; got " + paragraphs.length
                        + ":\n----\n" + out + "\n----");
        assertTrue(paragraphs[0].startsWith("Service '"),
                "paragraph 1 should be the Summary; was: " + paragraphs[0]);
        assertTrue(paragraphs[1].startsWith("Observed symptoms:"),
                "paragraph 2 should be Observed symptoms; was: " + paragraphs[1]);
        assertTrue(paragraphs[2].startsWith("Fired inference rules:"),
                "paragraph 3 should be Fired inference rules; was: " + paragraphs[2]);
        assertTrue(paragraphs[3].startsWith("Contributing factors"),
                "paragraph 4 should be Contributing factors; was: " + paragraphs[3]);
        assertTrue(paragraphs[4].startsWith("Causal propagation path:"),
                "paragraph 5 should be Causal propagation path; was: " + paragraphs[4]);
        assertTrue(paragraphs[5].startsWith("Recommended action:"),
                "paragraph 6 should be Recommended action; was: " + paragraphs[5]);
    }

    // ---------------------------------------------------------------------
    // CASCADING_FAILURE maps to ResourceContention
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("CASCADING_FAILURE maps to diagnostic:ResourceContention (closest semantic match)")
    void cascadingFailure_mapsToResourceContention() {
        String out = builder.explain(
                rankedCause("svc-y", "CASCADING_FAILURE"),
                vector("svc-y"),
                hypothesis("svc-y", "CASCADING_FAILURE"));
        assertTrue(out.contains("diagnostic:ResourceContention"),
                "expected CASCADING_FAILURE to map to diagnostic:ResourceContention; was:\n" + out);
    }

    // ---------------------------------------------------------------------
    // Unmapped category falls back gracefully (no exception)
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("Unmapped category falls back without throwing")
    void unmappedCategory_fallsBack() {
        String out = assertDoesNotThrow(() -> builder.explain(
                rankedCause("svc-z", "UNKNOWN"),
                vector("svc-z"),
                hypothesis("svc-z", "UNKNOWN")));
        assertNotNull(out);
        assertFalse(out.isBlank());
        assertTrue(out.contains("undetermined fault"),
                "expected fallback label 'undetermined fault'; was:\n" + out);
    }

    // ---------------------------------------------------------------------
    // Vocabulary table is exposed and complete
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("Vocabulary mapping table covers the six engine fault categories")
    void vocabularyMapping_coversAllCategories() {
        Map<String, String> table = OntologyGroundedExplanationBuilder.categoryToFaultLocalName();
        assertEquals(6, table.size());
        assertEquals("CpuSaturation",      table.get("CPU_SATURATION"));
        assertEquals("LatencySpike",       table.get("LATENCY_ANOMALY"));
        assertEquals("MemoryLeak",         table.get("MEMORY_PRESSURE"));
        assertEquals("HighErrorRate",      table.get("SERVICE_ERROR"));
        assertEquals("ResourceContention", table.get("RESOURCE_CONTENTION"));
        assertEquals("ResourceContention", table.get("CASCADING_FAILURE"));
    }

    // ---------------------------------------------------------------------
    // Test fixtures
    // ---------------------------------------------------------------------

    private static RankedCause rankedCause(String svc, String category) {
        return RankedCause.builder()
                .rank(1)
                .serviceId(svc)
                .finalConfidence(0.87)
                .localConfidence(0.74)
                .propagatedConfidence(0.13)
                .faultCategory(category)
                .causalPath(List.of("gateway", "order-svc", svc))
                .build();
    }

    private static FuzzyVector vector(String svc) {
        return FuzzyVector.builder()
                .serviceId(svc)
                .memberships(Map.of(
                        "cpu_HIGH",         0.82,
                        "latency_CRITICAL", 0.91,
                        "memory_HIGH",      0.55,
                        "errorRate_HIGH",   0.40))
                .build();
    }

    private static FaultHypothesis hypothesis(String svc, String category) {
        return FaultHypothesis.builder()
                .serviceId(svc)
                .localConfidence(0.74)
                .dominantFaultCategory(category)
                .firedRules(List.of("CPU_HIGH_LATENCY_HIGH"))
                .ruleFireStrengths(Map.of("CPU_HIGH_LATENCY_HIGH", 0.74))
                .build();
    }
}
