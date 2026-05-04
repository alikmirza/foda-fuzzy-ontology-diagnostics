package com.foda.rca.evaluation;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Schema-level test for {@link ExplanationComparisonRunner}.
 *
 * <p>Asserts the structural contract of the two CSV artefacts (headers, row counts,
 * builder coverage). Deliberately does <em>not</em> pin specific metric values — those
 * are the empirical results being measured and we don't want regression-test friction
 * if the metric or the scenarios are tuned.</p>
 */
@DisplayName("ExplanationComparisonRunner — CSV schema")
class ExplanationComparisonRunnerTest {

    private static final int    NUM_SCENARIOS = 12;   // FODA-12
    private static final int    NUM_BUILDERS  = 2;    // Legacy + OntologyGrounded

    @Test
    @DisplayName("Both CSVs are written with the expected headers and row counts")
    void writesBothCsvs(@TempDir Path tmpDir) throws IOException {
        Path perScenarioCsv = tmpDir.resolve("rca-explanation-comparison.csv");
        Path aggregatedCsv  = tmpDir.resolve("rca-explanation-comparison-aggregated.csv");

        ExplanationComparisonRunner.runAndWrite(perScenarioCsv, aggregatedCsv);

        assertTrue(Files.exists(perScenarioCsv), "per-scenario CSV must exist");
        assertTrue(Files.exists(aggregatedCsv),  "aggregated CSV must exist");
        assertFalse(Files.readString(perScenarioCsv).isBlank(),
                "per-scenario CSV must be non-empty");
        assertFalse(Files.readString(aggregatedCsv).isBlank(),
                "aggregated CSV must be non-empty");

        // ── Per-scenario CSV ─────────────────────────────────────────────
        List<String> perScenarioLines = Files.readAllLines(perScenarioCsv);
        // Drop trailing blank lines just in case.
        while (!perScenarioLines.isEmpty()
                && perScenarioLines.get(perScenarioLines.size() - 1).isBlank()) {
            perScenarioLines.remove(perScenarioLines.size() - 1);
        }
        assertEquals(ExplanationComparisonRunner.PER_SCENARIO_HEADER,
                perScenarioLines.get(0),
                "per-scenario CSV header must match the documented schema");
        // 12 scenarios × 2 builders = 24 data rows; +1 header = 25 total
        assertEquals(NUM_SCENARIOS * NUM_BUILDERS + 1, perScenarioLines.size(),
                "expected 1 header + (12 scenarios × 2 builders = 24) data rows");

        // Each builder appears exactly once per scenario (12 rows per builder)
        long legacyRows = perScenarioLines.stream().filter(l -> l.contains(",Legacy,")).count();
        long ontoRows   = perScenarioLines.stream().filter(l -> l.contains(",OntologyGrounded,")).count();
        assertEquals(NUM_SCENARIOS, legacyRows,
                "Legacy builder must contribute exactly 12 rows");
        assertEquals(NUM_SCENARIOS, ontoRows,
                "OntologyGrounded builder must contribute exactly 12 rows");

        // ── Aggregated CSV ───────────────────────────────────────────────
        List<String> aggregatedLines = Files.readAllLines(aggregatedCsv);
        while (!aggregatedLines.isEmpty()
                && aggregatedLines.get(aggregatedLines.size() - 1).isBlank()) {
            aggregatedLines.remove(aggregatedLines.size() - 1);
        }
        assertEquals(ExplanationComparisonRunner.AGGREGATED_HEADER,
                aggregatedLines.get(0),
                "aggregated CSV header must match the documented schema");
        // 2 builders → 2 data rows + 1 header = 3 total
        assertEquals(NUM_BUILDERS + 1, aggregatedLines.size(),
                "expected 1 header + 2 data rows (one per builder)");
        assertTrue(aggregatedLines.get(1).startsWith("Legacy,")
                || aggregatedLines.get(2).startsWith("Legacy,"),
                "Legacy builder row must be present in aggregated CSV");
        assertTrue(aggregatedLines.get(1).startsWith("OntologyGrounded,")
                || aggregatedLines.get(2).startsWith("OntologyGrounded,"),
                "OntologyGrounded builder row must be present in aggregated CSV");
    }

    @Test
    @DisplayName("Determinism: running the runner twice produces byte-identical CSVs")
    void deterministic(@TempDir Path tmpDir) throws IOException {
        Path psA = tmpDir.resolve("a-per.csv"), aggA = tmpDir.resolve("a-agg.csv");
        Path psB = tmpDir.resolve("b-per.csv"), aggB = tmpDir.resolve("b-agg.csv");

        ExplanationComparisonRunner.runAndWrite(psA, aggA);
        ExplanationComparisonRunner.runAndWrite(psB, aggB);

        assertEquals(Files.readString(psA),  Files.readString(psB),
                "per-scenario CSV must be byte-identical across runs");
        assertEquals(Files.readString(aggA), Files.readString(aggB),
                "aggregated CSV must be byte-identical across runs");
    }
}
