package com.foda.rca.evaluation;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.core.FuzzyRcaEngineImpl;
import com.foda.rca.propagation.LocalOnlyPropagator;
import com.foda.rca.propagation.MaxPropagationBaseline;
import com.foda.rca.propagation.UniformWeightPropagator;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * End-to-end benchmark execution for paper Section 5 (Table 4 reproduction).
 *
 * <p>Runs the five algorithms defined in README.md (FCP-RCA, -Damping, -Propagation,
 * -Weights, +MaxProp) over the FODA-8 standard benchmark suite and writes:
 * <ul>
 *   <li>{@code target/rca-results.csv}      — aggregated metrics, one row per algorithm</li>
 *   <li>{@code target/rca-per-scenario.csv} — per-(algorithm × scenario) metrics</li>
 *   <li>{@code target/rca-results.tex}      — LaTeX table ready to paste into the paper</li>
 * </ul>
 *
 * <p>Not part of the default Surefire include pattern — invoke explicitly with
 * {@code mvn test -Dtest=BenchmarkRunner}. Tagged {@code benchmark} so it can also
 * be enabled via JUnit Platform tag filters in CI.
 *
 * <p>Algorithm parameters are fixed for reproducibility: δ=0.85, ε=1e-6, max_iter=100, k=3.
 */
@Tag("benchmark")
public class BenchmarkRunner {

    private static final int K = 3;
    private static final Path OUTPUT_DIR = Path.of("target");

    @Test
    void runStandardBenchmarkAndExportArtifacts() throws IOException {
        Map<String, FuzzyRcaEngine> algorithms = new LinkedHashMap<>();
        algorithms.put("FCP-RCA",
                FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());
        algorithms.put("-Damping",
                FuzzyRcaEngineImpl.builder().withDampingFactor(1.0).build());
        algorithms.put("-Propagation",
                FuzzyRcaEngineImpl.builder().propagator(new LocalOnlyPropagator()).build());
        algorithms.put("-Weights",
                FuzzyRcaEngineImpl.builder().propagator(new UniformWeightPropagator(0.85)).build());
        algorithms.put("+MaxProp",
                FuzzyRcaEngineImpl.builder().propagator(new MaxPropagationBaseline()).build());

        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.standardBenchmarkSuite();

        RcaEvaluator evaluator = new RcaEvaluator();
        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, K);

        Path aggregatedCsv = evaluator.writeCsv(results, OUTPUT_DIR);
        Path perScenarioCsv = evaluator.writePerScenarioCsv(results, OUTPUT_DIR);

        Path latexFile = OUTPUT_DIR.resolve("rca-results.tex");
        Files.createDirectories(OUTPUT_DIR);
        Files.writeString(latexFile, evaluator.toLatexTable(results), StandardCharsets.UTF_8);

        assertTrue(Files.exists(aggregatedCsv),  "rca-results.csv must exist");
        assertTrue(Files.exists(perScenarioCsv), "rca-per-scenario.csv must exist");
        assertTrue(Files.exists(latexFile),      "rca-results.tex must exist");
        assertFalse(Files.readString(aggregatedCsv).isBlank(),  "rca-results.csv must be non-empty");
        assertFalse(Files.readString(perScenarioCsv).isBlank(), "rca-per-scenario.csv must be non-empty");
        assertFalse(Files.readString(latexFile).isBlank(),      "rca-results.tex must be non-empty");

        printConsoleSummary(results, aggregatedCsv, perScenarioCsv, latexFile);
    }

    private static void printConsoleSummary(Map<String, AggregatedEvaluation> results,
                                            Path aggregatedCsv,
                                            Path perScenarioCsv,
                                            Path latexFile) {
        System.out.println();
        System.out.println("=========================================================================");
        System.out.println(" FCP-RCA Benchmark Summary  (FODA-8 standard suite, k=" + K + ", n="
                + results.values().iterator().next().getNumScenarios() + " scenarios)");
        System.out.println("=========================================================================");
        System.out.printf("%-15s %8s %8s %8s %8s %8s%n",
                "Algorithm", "P@" + K, "R@" + K, "MRR", "NDCG@" + K, "Top-1");
        System.out.println("-------------------------------------------------------------------------");
        for (AggregatedEvaluation e : results.values()) {
            System.out.printf("%-15s %8.4f %8.4f %8.4f %8.4f %8.4f%n",
                    e.getAlgorithmName(),
                    e.getMeanPrecisionAtK(),
                    e.getMeanRecallAtK(),
                    e.getMeanMrr(),
                    e.getMeanNdcgAtK(),
                    e.getTop1Accuracy());
        }
        System.out.println("=========================================================================");
        System.out.println(" Aggregated CSV : " + aggregatedCsv.toAbsolutePath());
        System.out.println(" Per-scenario   : " + perScenarioCsv.toAbsolutePath());
        System.out.println(" LaTeX table    : " + latexFile.toAbsolutePath());
        System.out.println("=========================================================================");
        System.out.println();
    }
}
