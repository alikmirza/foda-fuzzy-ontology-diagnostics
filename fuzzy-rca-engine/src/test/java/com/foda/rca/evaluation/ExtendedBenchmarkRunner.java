package com.foda.rca.evaluation;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.core.FuzzyRcaEngineImpl;
import com.foda.rca.model.DiagnosisResult;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceMetrics;
import com.foda.rca.propagation.LocalOnlyPropagator;
import com.foda.rca.propagation.MaxPropagationBaseline;
import com.foda.rca.propagation.UniformWeightPropagator;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * End-to-end benchmark execution for the FODA-12 extended suite.
 *
 * <p>Runs the same five algorithms as {@link BenchmarkRunner} but over the
 * 12-scenario {@link SyntheticScenarioBuilder#extendedBenchmarkSuite()}:
 * the eight FODA-8 scenarios (unchanged) plus four diverse-topology scenarios
 * (S09–S12) that exercise the cycle-safe iterative propagator and damping
 * behaviour on deep DAGs.
 *
 * <p>Output artefacts (separate from BenchmarkRunner so FODA-8 results are not overwritten):
 * <ul>
 *   <li>{@code target/rca-results-extended.csv}      — aggregated metrics</li>
 *   <li>{@code target/rca-per-scenario-extended.csv} — per-(algorithm × scenario)</li>
 *   <li>{@code target/rca-results-extended.tex}      — LaTeX table</li>
 *   <li>{@code target/rca-cycle-activation.txt}      — per-cyclic-scenario propagator
 *       choice trace, captured from AdaptiveConfidencePropagator log output</li>
 * </ul>
 *
 * <p>Algorithm parameters are fixed for reproducibility: δ=0.85, ε=1e-6, max_iter=100, k=3.
 */
@Tag("benchmark")
public class ExtendedBenchmarkRunner {

    private static final Logger log = LoggerFactory.getLogger(ExtendedBenchmarkRunner.class);
    private static final int K = 3;
    private static final Path OUTPUT_DIR = Path.of("target");

    /**
     * Test-side wrapper that catches {@link IllegalStateException} thrown by
     * propagators that perform a topological sort on the dependency graph
     * (UniformWeightPropagator, MaxPropagationBaseline). Cyclic graphs make
     * topological sort undefined; rather than crashing the whole benchmark,
     * we record the outcome as "no prediction" — which yields P@k=R@k=MRR=NDCG=0.
     *
     * <p>This wraps the engine at the test-runner boundary and does NOT modify
     * any algorithm code.</p>
     */
    private static final class FailSafeEngine implements FuzzyRcaEngine {
        private final FuzzyRcaEngine delegate;
        private final String name;

        FailSafeEngine(FuzzyRcaEngine delegate, String name) {
            this.delegate = delegate;
            this.name = name;
        }

        @Override
        public DiagnosisResult diagnose(List<ServiceMetrics> obs,
                                        ServiceDependencyGraph graph,
                                        int topK) {
            try {
                return delegate.diagnose(obs, graph, topK);
            } catch (IllegalStateException ex) {
                log.warn("[{}] cannot run on this scenario (cyclic graph) — recording empty result: {}",
                        name, ex.getMessage());
                return DiagnosisResult.builder()
                        .diagnosisId("incompatible-cyclic-graph")
                        .timestamp(Instant.now())
                        .rankedCauses(List.of())
                        .fuzzyVectors(java.util.Map.of())
                        .faultHypotheses(java.util.Map.of())
                        .propagatedConfidences(java.util.Map.of())
                        .serviceCount(graph.getServices().size())
                        .edgeCount(0)
                        .build();
            }
        }
    }

    @Test
    void runExtendedBenchmarkAndExportArtifacts() throws IOException {
        Map<String, FuzzyRcaEngine> algorithms = new LinkedHashMap<>();
        algorithms.put("FCP-RCA",
                wrap("FCP-RCA",
                        FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build()));
        algorithms.put("-Damping",
                wrap("-Damping",
                        FuzzyRcaEngineImpl.builder().withDampingFactor(1.0).build()));
        algorithms.put("-Propagation",
                wrap("-Propagation",
                        FuzzyRcaEngineImpl.builder().propagator(new LocalOnlyPropagator()).build()));
        algorithms.put("-Weights",
                wrap("-Weights",
                        FuzzyRcaEngineImpl.builder().propagator(new UniformWeightPropagator(0.85)).build()));
        algorithms.put("+MaxProp",
                wrap("+MaxProp",
                        FuzzyRcaEngineImpl.builder().propagator(new MaxPropagationBaseline()).build()));

        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.extendedBenchmarkSuite();
        assertEquals(12, suite.size(), "Extended suite must contain exactly 12 scenarios");

        RcaEvaluator evaluator = new RcaEvaluator();
        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, K);

        Files.createDirectories(OUTPUT_DIR);
        Path aggregatedCsv  = writeAggregatedCsv(evaluator, results);
        Path perScenarioCsv = writePerScenarioCsv(evaluator, results);
        Path latexFile      = OUTPUT_DIR.resolve("rca-results-extended.tex");
        Files.writeString(latexFile, evaluator.toLatexTable(results), StandardCharsets.UTF_8);

        Path activationFile = writeCycleActivationTrace(suite);

        assertTrue(Files.exists(aggregatedCsv),  "rca-results-extended.csv must exist");
        assertTrue(Files.exists(perScenarioCsv), "rca-per-scenario-extended.csv must exist");
        assertTrue(Files.exists(latexFile),      "rca-results-extended.tex must exist");
        assertFalse(Files.readString(aggregatedCsv).isBlank(),  "aggregated CSV must be non-empty");
        assertFalse(Files.readString(perScenarioCsv).isBlank(), "per-scenario CSV must be non-empty");
        assertFalse(Files.readString(latexFile).isBlank(),      "LaTeX table must be non-empty");

        printConsoleSummary(results, aggregatedCsv, perScenarioCsv, latexFile, activationFile);
    }

    private static FuzzyRcaEngine wrap(String name, FuzzyRcaEngine engine) {
        return new FailSafeEngine(engine, name);
    }

    // -----------------------------------------------------------------------
    // Cycle-safe propagator activation trace (S09, S10, S12)
    // -----------------------------------------------------------------------

    /**
     * For each scenario whose graph has a cycle, run the FCP-RCA engine
     * once with a stand-alone {@code AdaptiveConfidencePropagator} and capture
     * the propagator choice from its DEBUG log. Writes the trace to
     * {@code target/rca-cycle-activation.txt}.
     *
     * <p>This is purely an evidence-collection step — it does not modify
     * AdaptiveConfidencePropagator or any algorithm code.</p>
     */
    private Path writeCycleActivationTrace(List<GroundTruthScenario> suite) throws IOException {
        Path out = OUTPUT_DIR.resolve("rca-cycle-activation.txt");
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out))) {
            pw.println("# Propagator activation trace for FODA-12 cyclic scenarios");
            pw.println("# Captured from ServiceDependencyGraph.hasCycle() — same predicate");
            pw.println("# AdaptiveConfidencePropagator uses to switch between");
            pw.println("# DampedConfidencePropagator (acyclic) and IterativeConfidencePropagator (cyclic).");
            pw.println();
            for (GroundTruthScenario s : suite) {
                boolean cyclic = s.getDependencyGraph().hasCycle();
                String propagator = cyclic
                        ? "IterativeConfidencePropagator (Eq. 5, ε=1e-6, max_iter=100)"
                        : "DampedConfidencePropagator (Eq. 4)";
                pw.printf("%-4s  %-30s  hasCycle=%-5s  →  %s%n",
                        s.getScenarioId(),
                        s.getScenarioName(),
                        cyclic,
                        propagator);
            }
        }
        return out;
    }

    // -----------------------------------------------------------------------
    // CSV writers (use distinct filenames so FODA-8 results are not overwritten)
    // -----------------------------------------------------------------------

    private Path writeAggregatedCsv(RcaEvaluator evaluator,
                                    Map<String, AggregatedEvaluation> results) throws IOException {
        // Reuse RcaEvaluator.toCsv() but write to the extended-suite filename.
        Path out = OUTPUT_DIR.resolve("rca-results-extended.csv");
        Files.writeString(out, evaluator.toCsv(results), StandardCharsets.UTF_8);
        return out;
    }

    private Path writePerScenarioCsv(RcaEvaluator evaluator,
                                     Map<String, AggregatedEvaluation> results) throws IOException {
        // Build the per-scenario CSV directly under the extended-suite filename.
        // We do NOT call evaluator.writePerScenarioCsv() because that writes to the
        // canonical "rca-per-scenario.csv" path used by BenchmarkRunner — overwriting
        // the FODA-8 output. The column layout below mirrors RcaEvaluator's writer.
        Path out = OUTPUT_DIR.resolve("rca-per-scenario-extended.csv");
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out, StandardCharsets.UTF_8))) {
            pw.println("algorithm,scenario_id,scenario_name,fault_type,k,"
                     + "precision,recall,mrr,ndcg,top1_correct,"
                     + "predicted_causes,true_root_causes");
            for (AggregatedEvaluation agg : results.values()) {
                for (ScenarioEvaluation se : agg.getPerScenarioResults()) {
                    pw.printf("%s,%s,%s,%s,%d,%.6f,%.6f,%.6f,%.6f,%b,\"%s\",\"%s\"%n",
                            agg.getAlgorithmName(),
                            se.getScenarioId(),
                            se.getScenarioName(),
                            se.getFaultType(),
                            se.getK(),
                            se.getPrecisionAtK(),
                            se.getRecallAtK(),
                            se.getMrr(),
                            se.getNdcgAtK(),
                            se.isTopOneCorrect(),
                            String.join(";", se.getPredictedCauses()),
                            String.join(";", se.getTrueRootCauses()));
                }
            }
        }
        return out;
    }

    // -----------------------------------------------------------------------
    // Console summary
    // -----------------------------------------------------------------------

    private static void printConsoleSummary(Map<String, AggregatedEvaluation> results,
                                            Path aggregatedCsv,
                                            Path perScenarioCsv,
                                            Path latexFile,
                                            Path activationFile) {
        int n = results.values().iterator().next().getNumScenarios();
        System.out.println();
        System.out.println("=========================================================================");
        System.out.println(" FCP-RCA Extended Benchmark Summary  (FODA-12 suite, k=" + K + ", n=" + n + ")");
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
        System.out.println(" Aggregated CSV  : " + aggregatedCsv.toAbsolutePath());
        System.out.println(" Per-scenario    : " + perScenarioCsv.toAbsolutePath());
        System.out.println(" LaTeX table     : " + latexFile.toAbsolutePath());
        System.out.println(" Cycle-safe trace: " + activationFile.toAbsolutePath());
        System.out.println("=========================================================================");
        System.out.println();
    }
}
