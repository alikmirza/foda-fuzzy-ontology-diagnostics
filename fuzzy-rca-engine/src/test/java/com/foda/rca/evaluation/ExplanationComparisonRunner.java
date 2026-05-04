package com.foda.rca.evaluation;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.core.FuzzyRcaEngineImpl;
import com.foda.rca.explanation.ExplanationBuilder;
import com.foda.rca.explanation.NaturalLanguageExplanationBuilder;
import com.foda.rca.explanation.OntologyGroundedExplanationBuilder;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Explanation-quality comparison runner.
 *
 * <p>Runs the same FCP-RCA pipeline (default damped configuration, δ=0.85) twice over the
 * full FODA-12 scenario suite, varying only the explanation builder:</p>
 * <ol>
 *   <li><strong>Legacy</strong> — {@link NaturalLanguageExplanationBuilder} (template-only baseline).</li>
 *   <li><strong>OntologyGrounded</strong> — {@link OntologyGroundedExplanationBuilder} (proposed).</li>
 * </ol>
 *
 * <p>For each (scenario × builder) pair we record both the standard ranking metric
 * (Top-1 accuracy) and the four-component {@link ExplanationQualityMetric} sub-scores.
 * Two CSV artefacts land in {@code target/}:</p>
 * <ul>
 *   <li>{@code rca-explanation-comparison.csv} — per-scenario rows
 *       (24 data rows = 12 scenarios × 2 builders).</li>
 *   <li>{@code rca-explanation-comparison-aggregated.csv} — one row per builder
 *       (2 data rows). This is the table that lands in the paper's main
 *       results section.</li>
 * </ul>
 *
 * <p><strong>Determinism:</strong> the FCP-RCA engine is deterministic, both explanation
 * builders are deterministic, and the metric is deterministic — running this method twice
 * produces byte-identical CSVs.</p>
 *
 * <p>The original {@link ExtendedBenchmarkRunner} is left untouched: this runner targets a
 * different question (explanation quality) and a different output directory schema, so the
 * FODA-12 ranking results in {@code rca-results-extended.csv} are not affected.</p>
 */
@Tag("benchmark")
public class ExplanationComparisonRunner {

    private static final Logger log = LoggerFactory.getLogger(ExplanationComparisonRunner.class);

    private static final int    K          = 3;
    private static final Path   OUTPUT_DIR = Path.of("target");

    private static final String PER_SCENARIO_FILE = "rca-explanation-comparison.csv";
    private static final String AGGREGATED_FILE   = "rca-explanation-comparison-aggregated.csv";

    static final String PER_SCENARIO_HEADER =
            "scenario_id,scenario_name,builder,top_1_correct,faithfulness,coverage,"
            + "conciseness,semantic_groundedness,overall_explanation_score";

    static final String AGGREGATED_HEADER =
            "builder,mean_top_1_correct,mean_faithfulness,mean_coverage,mean_conciseness,"
            + "mean_semantic_groundedness,mean_overall";

    @Test
    void runExplanationComparisonAndExportArtifacts() throws IOException {
        Path perScenarioCsv = OUTPUT_DIR.resolve(PER_SCENARIO_FILE);
        Path aggregatedCsv  = OUTPUT_DIR.resolve(AGGREGATED_FILE);
        runAndWrite(perScenarioCsv, aggregatedCsv);

        // Smoke assertions; full schema-level checks live in the dedicated test class.
        assertTrue(Files.exists(perScenarioCsv), PER_SCENARIO_FILE + " must exist");
        assertTrue(Files.exists(aggregatedCsv),  AGGREGATED_FILE   + " must exist");
    }

    /**
     * Public entry point that the dedicated test class can invoke against a temp directory
     * without going through the {@code @Test} method's hard-coded {@code target/} output.
     *
     * @param perScenarioCsv path of the per-scenario CSV to write
     * @param aggregatedCsv  path of the aggregated CSV to write
     */
    public static void runAndWrite(Path perScenarioCsv, Path aggregatedCsv) throws IOException {
        Files.createDirectories(perScenarioCsv.getParent() == null
                ? Path.of(".")
                : perScenarioCsv.getParent());

        // Both runs use the same engine configuration — only the explanation builder
        // varies. We build two engines rather than mutating one to keep behaviour
        // visibly side-effect-free.
        Map<String, ExplanationBuilder> builders = new LinkedHashMap<>();
        builders.put("Legacy",           new NaturalLanguageExplanationBuilder());
        builders.put("OntologyGrounded", new OntologyGroundedExplanationBuilder());

        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.extendedBenchmarkSuite();
        assertEquals(12, suite.size(),
                "Expected 12 FODA-12 scenarios; ExplanationComparisonRunner depends on the suite shape");

        ExplanationQualityMetric metric = new ExplanationQualityMetric();
        RcaEvaluator evaluator = new RcaEvaluator(metric);

        // Per-builder aggregated results, computed via the standard RcaEvaluator pipeline
        // so ranking metrics stay in lockstep with the rest of the benchmark suite.
        Map<String, AggregatedEvaluation> aggregated = new LinkedHashMap<>();
        for (Map.Entry<String, ExplanationBuilder> e : builders.entrySet()) {
            String label = e.getKey();
            FuzzyRcaEngine engine = FuzzyRcaEngineImpl.builder()
                    .withDampingFactor(0.85)
                    .explanationBuilder(e.getValue())
                    .build();
            log.info("Evaluating builder '{}' on FODA-12 (k={}, n={})...", label, K, suite.size());
            aggregated.put(label, evaluator.aggregate(engine, label, suite, K));
        }

        writePerScenarioCsv(aggregated, perScenarioCsv);
        writeAggregatedCsv(aggregated, aggregatedCsv);
        printConsoleSummary(aggregated, perScenarioCsv, aggregatedCsv);
    }

    // ---------------------------------------------------------------------
    // CSV writers
    // ---------------------------------------------------------------------

    private static void writePerScenarioCsv(Map<String, AggregatedEvaluation> results,
                                             Path out) throws IOException {
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out, StandardCharsets.UTF_8))) {
            pw.println(PER_SCENARIO_HEADER);
            for (AggregatedEvaluation agg : results.values()) {
                String builder = agg.getAlgorithmName();
                for (ScenarioEvaluation se : agg.getPerScenarioResults()) {
                    pw.printf("%s,%s,%s,%b,%s,%s,%s,%s,%s%n",
                            se.getScenarioId(),
                            se.getScenarioName(),
                            builder,
                            se.isTopOneCorrect(),
                            fmt(se.getFaithfulness()),
                            fmt(se.getCoverage()),
                            fmt(se.getConciseness()),
                            fmt(se.getSemanticGroundedness()),
                            fmt(se.getOverallExplanationScore()));
                }
            }
        }
    }

    private static void writeAggregatedCsv(Map<String, AggregatedEvaluation> results,
                                            Path out) throws IOException {
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out, StandardCharsets.UTF_8))) {
            pw.println(AGGREGATED_HEADER);
            for (AggregatedEvaluation agg : results.values()) {
                pw.printf("%s,%s,%s,%s,%s,%s,%s%n",
                        agg.getAlgorithmName(),
                        fmt(agg.getTop1Accuracy()),
                        fmt(agg.getMeanFaithfulness()),
                        fmt(agg.getMeanCoverage()),
                        fmt(agg.getMeanConciseness()),
                        fmt(agg.getMeanSemanticGroundedness()),
                        fmt(agg.getMeanOverallExplanationScore()));
            }
        }
    }

    private static String fmt(double v) {
        return Double.isNaN(v) ? "NaN" : String.format("%.6f", v);
    }

    // ---------------------------------------------------------------------
    // Console summary
    // ---------------------------------------------------------------------

    private static void printConsoleSummary(Map<String, AggregatedEvaluation> results,
                                             Path perScenarioCsv,
                                             Path aggregatedCsv) {
        System.out.println();
        System.out.println("==================================================================================");
        System.out.println(" FCP-RCA Explanation-Quality Comparison  (FODA-12, k=" + K + ")");
        System.out.println("==================================================================================");
        System.out.printf("%-18s %8s %8s %8s %8s %8s %8s%n",
                "Builder", "Top-1", "Faith", "Cov", "Conc", "Ground", "Overall");
        System.out.println("----------------------------------------------------------------------------------");
        for (AggregatedEvaluation e : results.values()) {
            System.out.printf("%-18s %8.4f %8.4f %8.4f %8.4f %8.4f %8.4f%n",
                    e.getAlgorithmName(),
                    e.getTop1Accuracy(),
                    e.getMeanFaithfulness(),
                    e.getMeanCoverage(),
                    e.getMeanConciseness(),
                    e.getMeanSemanticGroundedness(),
                    e.getMeanOverallExplanationScore());
        }
        System.out.println("==================================================================================");
        System.out.println(" Per-scenario CSV : " + perScenarioCsv.toAbsolutePath());
        System.out.println(" Aggregated CSV   : " + aggregatedCsv.toAbsolutePath());
        System.out.println("==================================================================================");
        System.out.println();
    }
}
