package com.foda.rca.evaluation;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.model.DiagnosisResult;
import com.foda.rca.model.RankedCause;
import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Experimental evaluation engine for RCA algorithm comparison (Section 5).
 *
 * <p>Computes the four standard information-retrieval metrics used in microservice RCA
 * benchmarks (Chen et al. 2019, Ma et al. 2020, Ikram et al. 2022):
 * Precision@k, Recall@k, MRR, and NDCG@k.</p>
 *
 * <h2>Usage pattern (Section 5.2)</h2>
 * <pre>
 *   // Build algorithms under comparison
 *   Map&lt;String, FuzzyRcaEngine&gt; algorithms = new LinkedHashMap&lt;&gt;();
 *   algorithms.put("FCP-RCA",   FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());
 *   algorithms.put("-Damping",  FuzzyRcaEngineImpl.builder().build());   // δ=1 baseline
 *   algorithms.put("-Prop",     FuzzyRcaEngineImpl.builder()
 *                                  .propagator(new LocalOnlyPropagator()).build());
 *   algorithms.put("-Weights",  FuzzyRcaEngineImpl.builder()
 *                                  .propagator(new UniformWeightPropagator()).build());
 *
 *   // Load scenarios
 *   ServiceDependencyGraph graph = ...;
 *   List&lt;GroundTruthScenario&gt; suite = SyntheticScenarioBuilder.standardBenchmarkSuite(graph);
 *
 *   // Evaluate and print LaTeX table
 *   RcaEvaluator evaluator = new RcaEvaluator();
 *   Map&lt;String, AggregatedEvaluation&gt; results = evaluator.compare(algorithms, suite, 3);
 *   System.out.println(evaluator.toLatexTable(results));
 * </pre>
 *
 * <h2>Metric formulas (Equations 6–9, Section 5.2)</h2>
 * <pre>
 *   P@k  = |top_k ∩ R| / min(k, |top_k|)                      [Eq. 6]
 *   R@k  = |top_k ∩ R| / |R|                                   [Eq. 7]
 *   MRR  = 1 / rank(first r ∈ R)                               [Eq. 8]
 *   NDCG@k = DCG@k / IDCG@k                                    [Eq. 9]
 *     where DCG@k  = ∑_{i=1}^{k} rel_i / log2(i+1),
 *           IDCG@k = ∑_{i=1}^{min(k,|R|)} 1 / log2(i+1)
 * </pre>
 */
@Slf4j
public class RcaEvaluator {

    /**
     * Optional per-explanation quality scorer. When non-null, {@link #evaluate} also
     * computes {@link ExplanationQualityMetric#evaluate} for the top-1 candidate's
     * explanation text and writes the result into the returned {@link ScenarioEvaluation}.
     * When {@code null}, the evaluator behaves exactly as before — no explanation work,
     * no extra fields populated. Existing benchmark code uses the no-arg constructor and
     * is therefore unaffected.
     */
    private final ExplanationQualityMetric explanationMetric;

    /** Default constructor: no explanation scoring (backward-compatible behaviour). */
    public RcaEvaluator() {
        this.explanationMetric = null;
    }

    /**
     * Constructor with an optional explanation-quality metric.
     *
     * @param explanationMetric metric instance (e.g. {@code new ExplanationQualityMetric()}),
     *                          or {@code null} to disable explanation scoring. The instance
     *                          itself is currently stateless, but is accepted as a typed
     *                          dependency so future stateful variants (e.g. with custom
     *                          stop-word lists or weights) can be wired in without changing
     *                          this signature.
     */
    public RcaEvaluator(ExplanationQualityMetric explanationMetric) {
        this.explanationMetric = explanationMetric;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Evaluate a single algorithm on a single scenario.
     *
     * @param engine   the RCA engine to evaluate
     * @param name     algorithm name for labelling
     * @param scenario the ground-truth scenario
     * @param k        number of top predictions to consider
     * @return per-scenario evaluation metrics
     */
    public ScenarioEvaluation evaluate(FuzzyRcaEngine engine,
                                        String name,
                                        GroundTruthScenario scenario,
                                        int k) {
        DiagnosisResult result = engine.diagnose(
                scenario.getObservations(), scenario.getDependencyGraph(), k);

        List<String> predicted = result.getRankedCauses().stream()
                .map(RankedCause::getServiceId)
                .collect(Collectors.toList());

        Set<String> truth = scenario.getTrueRootCauses();

        double precision = precisionAtK(predicted, truth, k);
        double recall    = recallAtK(predicted, truth, k);
        double mrrVal    = mrr(predicted, truth);
        double ndcg      = ndcgAtK(predicted, truth, k);
        boolean top1     = !predicted.isEmpty() && truth.contains(predicted.get(0));

        ScenarioEvaluation.ScenarioEvaluationBuilder builder = ScenarioEvaluation.builder()
                .scenarioId(scenario.getScenarioId())
                .scenarioName(scenario.getScenarioName())
                .algorithmName(name)
                .k(k)
                .precisionAtK(precision)
                .recallAtK(recall)
                .mrr(mrrVal)
                .ndcgAtK(ndcg)
                .predictedCauses(predicted)
                .trueRootCauses(truth)
                .topOneCorrect(top1)
                .faultType(scenario.getFaultType());

        // Optional explanation scoring: only when a metric is configured AND the
        // engine produced at least one ranked cause carrying an explanation string.
        if (explanationMetric != null && !result.getRankedCauses().isEmpty()) {
            RankedCause topCause = result.getRankedCauses().get(0);
            String explanation = topCause.getExplanation();
            List<String> renderedPath = topCause.getCausalPath() != null
                    ? topCause.getCausalPath()
                    : List.of();
            ExplanationScore score = ExplanationQualityMetric.evaluate(
                    explanation, scenario, renderedPath);
            builder.faithfulness(score.getFaithfulness())
                   .coverage(score.getCoverage())
                   .conciseness(score.getConciseness())
                   .semanticGroundedness(score.getSemanticGroundedness())
                   .overallExplanationScore(score.getOverall());
        }

        return builder.build();
    }

    /**
     * Evaluate a single algorithm across all scenarios and aggregate results.
     *
     * @param engine    the RCA engine to evaluate
     * @param name      algorithm name
     * @param scenarios list of ground-truth scenarios
     * @param k         @k parameter
     * @return aggregated metrics with mean ± std for all metrics
     */
    public AggregatedEvaluation aggregate(FuzzyRcaEngine engine,
                                           String name,
                                           List<GroundTruthScenario> scenarios,
                                           int k) {
        if (scenarios == null || scenarios.isEmpty())
            throw new IllegalArgumentException("scenarios must not be empty");

        List<ScenarioEvaluation> perScenario = scenarios.stream()
                .map(s -> evaluate(engine, name, s, k))
                .collect(Collectors.toList());

        return aggregate(name, k, perScenario);
    }

    /**
     * Compare multiple algorithms on the same scenario suite.
     *
     * @param algorithms map of algorithmName → engine
     * @param scenarios  list of ground-truth scenarios
     * @param k          @k parameter
     * @return map of algorithmName → aggregated evaluation (insertion-ordered)
     */
    public Map<String, AggregatedEvaluation> compare(Map<String, FuzzyRcaEngine> algorithms,
                                                       List<GroundTruthScenario> scenarios,
                                                       int k) {
        if (algorithms == null || algorithms.isEmpty())
            throw new IllegalArgumentException("algorithms must not be empty");

        Map<String, AggregatedEvaluation> results = new LinkedHashMap<>();
        for (Map.Entry<String, FuzzyRcaEngine> entry : algorithms.entrySet()) {
            log.info("Evaluating '{}' on {} scenarios (k={}) ...",
                     entry.getKey(), scenarios.size(), k);
            results.put(entry.getKey(),
                        aggregate(entry.getValue(), entry.getKey(), scenarios, k));
        }
        return Collections.unmodifiableMap(results);
    }

    /**
     * Render comparison results as a publication-ready LaTeX table (Table 4 of the paper).
     *
     * @param results map returned by {@link #compare}
     * @return LaTeX table string ready to paste into the paper source
     */
    public String toLatexTable(Map<String, AggregatedEvaluation> results) {
        if (results.isEmpty()) return "";

        int k = results.values().iterator().next().getK();

        StringBuilder sb = new StringBuilder();
        sb.append("\\begin{table}[htbp]\n")
          .append("  \\centering\n")
          .append(String.format(
              "  \\caption{Comparison of RCA algorithms on the benchmark suite (k=%d)}\n", k))
          .append("  \\label{tab:rca-comparison}\n")
          .append(String.format(
              "  \\begin{tabular}{l|cccc|c}\n"
              + "    \\hline\n"
              + "    Algorithm & P@%d & R@%d & MRR & NDCG@%d & Top-1 Acc. \\\\\n"
              + "    \\hline\\hline\n", k, k, k));

        for (AggregatedEvaluation e : results.values()) {
            sb.append("    ").append(e.toLatexRow()).append("\n");
        }

        sb.append("  \\end{tabular}\n")
          .append("\\end{table}");
        return sb.toString();
    }

    // -----------------------------------------------------------------------
    // CSV output
    // -----------------------------------------------------------------------

    /**
     * Renders comparison results as a CSV string (aggregated, one row per algorithm).
     *
     * <p>Column order: {@code algorithm, k, n_scenarios, mean_precision, std_precision,
     * mean_recall, std_recall, mean_mrr, std_mrr, mean_ndcg, std_ndcg, top1_accuracy}.</p>
     *
     * @param results map returned by {@link #compare}
     * @return CSV string with header row followed by one data row per algorithm
     */
    public String toCsv(Map<String, AggregatedEvaluation> results) {
        if (results.isEmpty()) return AggregatedEvaluation.csvHeader();
        StringBuilder sb = new StringBuilder(AggregatedEvaluation.csvHeader()).append('\n');
        results.values().forEach(e -> sb.append(e.toCsvRow()).append('\n'));
        return sb.toString();
    }

    /**
     * Writes aggregated comparison results to {@code {outputDir}/rca-results.csv}.
     *
     * <p>The directory is created if it does not exist. This is the canonical output path
     * used when running the evaluation from Maven (output goes to {@code target/}).</p>
     *
     * @param results   map returned by {@link #compare}
     * @param outputDir directory to write the CSV file into (e.g. {@code Path.of("target")})
     * @return path of the written file
     * @throws java.io.UncheckedIOException if the file cannot be written
     */
    public Path writeCsv(Map<String, AggregatedEvaluation> results, Path outputDir) {
        try {
            Files.createDirectories(outputDir);
            Path out = outputDir.resolve("rca-results.csv");
            try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out))) {
                pw.print(toCsv(results));
            }
            log.info("Evaluation results written to {}", out.toAbsolutePath());
            return out;
        } catch (IOException e) {
            throw new java.io.UncheckedIOException("Failed to write CSV to " + outputDir, e);
        }
    }

    /**
     * Writes per-scenario evaluation results to {@code {outputDir}/rca-per-scenario.csv}.
     *
     * <p>Columns: {@code algorithm, scenario_id, scenario_name, fault_type, k,
     * precision, recall, mrr, ndcg, top1_correct, predicted_causes, true_root_causes,
     * faithfulness, coverage, conciseness, semantic_groundedness, overall_explanation_score}.
     * The five trailing explanation columns render as the literal {@code NaN} when no
     * explanation metric was configured.</p>
     *
     * @param results   map returned by {@link #compare}
     * @param outputDir directory to write into
     * @return path of the written file
     * @throws java.io.UncheckedIOException if the file cannot be written
     */
    public Path writePerScenarioCsv(Map<String, AggregatedEvaluation> results, Path outputDir) {
        try {
            Files.createDirectories(outputDir);
            Path out = outputDir.resolve("rca-per-scenario.csv");
            try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out))) {
                pw.println("algorithm,scenario_id,scenario_name,fault_type,k,"
                         + "precision,recall,mrr,ndcg,top1_correct,"
                         + "predicted_causes,true_root_causes,"
                         + "faithfulness,coverage,conciseness,"
                         + "semantic_groundedness,overall_explanation_score");
                for (AggregatedEvaluation agg : results.values()) {
                    for (ScenarioEvaluation se : agg.getPerScenarioResults()) {
                        pw.printf("%s,%s,%s,%s,%d,%.6f,%.6f,%.6f,%.6f,%b,\"%s\",\"%s\",%s,%s,%s,%s,%s%n",
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
                            String.join(";", se.getTrueRootCauses()),
                            fmt(se.getFaithfulness()),
                            fmt(se.getCoverage()),
                            fmt(se.getConciseness()),
                            fmt(se.getSemanticGroundedness()),
                            fmt(se.getOverallExplanationScore()));
                    }
                }
            }
            log.info("Per-scenario results written to {}", out.toAbsolutePath());
            return out;
        } catch (IOException e) {
            throw new java.io.UncheckedIOException("Failed to write per-scenario CSV to " + outputDir, e);
        }
    }

    /** CSV-friendly numeric formatter; NaN renders as {@code "NaN"} so column count is preserved. */
    private static String fmt(double v) {
        return Double.isNaN(v) ? "NaN" : String.format("%.6f", v);
    }

    // -----------------------------------------------------------------------
    // Metric calculations
    // -----------------------------------------------------------------------

    /**
     * Precision@k = |{top_k} ∩ R| / min(k, |{top_k}|).
     *
     * <p>Divides by min(k, |predicted|) rather than always k, so that shorter result
     * lists are not unfairly penalised (relevant for healthy-system scenarios where
     * the engine correctly returns zero candidates).</p>
     */
    public static double precisionAtK(List<String> predicted, Set<String> truth, int k) {
        if (predicted.isEmpty()) return 0.0;
        List<String> topK   = predicted.subList(0, Math.min(k, predicted.size()));
        long   hits         = topK.stream().filter(truth::contains).count();
        return (double) hits / topK.size();
    }

    /**
     * Recall@k = |{top_k} ∩ R| / |R|.
     */
    public static double recallAtK(List<String> predicted, Set<String> truth, int k) {
        if (truth.isEmpty()) return 1.0; // vacuously true: nothing to recall
        if (predicted.isEmpty()) return 0.0;
        List<String> topK = predicted.subList(0, Math.min(k, predicted.size()));
        long hits          = topK.stream().filter(truth::contains).count();
        return (double) hits / truth.size();
    }

    /**
     * Mean Reciprocal Rank = 1 / rank(first element of truth in predicted list).
     * Returns 0 if no true root cause appears in the predicted list.
     */
    public static double mrr(List<String> predicted, Set<String> truth) {
        for (int i = 0; i < predicted.size(); i++) {
            if (truth.contains(predicted.get(i))) return 1.0 / (i + 1);
        }
        return 0.0;
    }

    /**
     * NDCG@k = DCG@k / IDCG@k.
     *
     * <pre>
     *   DCG@k  = ∑_{i=1}^{k} rel_i / log2(i+1)
     *   IDCG@k = ∑_{i=1}^{min(k,|R|)} 1 / log2(i+1)  (ideal: all true causes at top)
     * </pre>
     *
     * Returns 0 when truth is empty or predicted is empty, 1 when perfect ranking.
     */
    public static double ndcgAtK(List<String> predicted, Set<String> truth, int k) {
        if (truth.isEmpty() || predicted.isEmpty()) return 0.0;
        List<String> topK  = predicted.subList(0, Math.min(k, predicted.size()));

        double dcg  = 0.0;
        for (int i = 0; i < topK.size(); i++) {
            if (truth.contains(topK.get(i))) {
                dcg += 1.0 / (Math.log(i + 2) / Math.log(2)); // log2(rank+1)
            }
        }

        double idcg = 0.0;
        int idealHits = Math.min(k, truth.size());
        for (int i = 0; i < idealHits; i++) {
            idcg += 1.0 / (Math.log(i + 2) / Math.log(2));
        }

        return idcg == 0 ? 0.0 : dcg / idcg;
    }

    // -----------------------------------------------------------------------
    // Internal aggregation
    // -----------------------------------------------------------------------

    private static AggregatedEvaluation aggregate(String name, int k,
                                                   List<ScenarioEvaluation> perScenario) {
        int n = perScenario.size();

        double[] p     = perScenario.stream().mapToDouble(ScenarioEvaluation::getPrecisionAtK).toArray();
        double[] r     = perScenario.stream().mapToDouble(ScenarioEvaluation::getRecallAtK).toArray();
        double[] mrrA  = perScenario.stream().mapToDouble(ScenarioEvaluation::getMrr).toArray();
        double[] ndcgA = perScenario.stream().mapToDouble(ScenarioEvaluation::getNdcgAtK).toArray();

        long top1Correct = perScenario.stream().filter(ScenarioEvaluation::isTopOneCorrect).count();

        // Per-fault-type NDCG breakdown
        Map<String, Double> ndcgByType = new LinkedHashMap<>();
        perScenario.stream()
            .filter(s -> s.getFaultType() != null)
            .collect(Collectors.groupingBy(
                ScenarioEvaluation::getFaultType,
                Collectors.averagingDouble(ScenarioEvaluation::getNdcgAtK)))
            .forEach(ndcgByType::put);

        AggregatedEvaluation.AggregatedEvaluationBuilder agg = AggregatedEvaluation.builder()
                .algorithmName(name)
                .k(k)
                .numScenarios(n)
                .meanPrecisionAtK(mean(p)).stdPrecisionAtK(std(p))
                .meanRecallAtK(mean(r)).stdRecallAtK(std(r))
                .meanMrr(mean(mrrA)).stdMrr(std(mrrA))
                .meanNdcgAtK(mean(ndcgA)).stdNdcgAtK(std(ndcgA))
                .top1Accuracy((double) top1Correct / n)
                .ndcgByFaultType(ndcgByType)
                .perScenarioResults(Collections.unmodifiableList(perScenario));

        // Optional explanation-quality aggregates: only produced when at least one
        // per-scenario evaluation carries a (finite) explanation score. Means are
        // computed across exactly those scenarios with a score; scenarios without
        // a score (engine returned no candidates → no explanation to evaluate)
        // are excluded rather than treated as zero.
        long scoredScenarios = perScenario.stream()
                .filter(ScenarioEvaluation::hasExplanationScore)
                .count();
        if (scoredScenarios > 0) {
            double[] f  = perScenario.stream().filter(ScenarioEvaluation::hasExplanationScore)
                    .mapToDouble(ScenarioEvaluation::getFaithfulness).toArray();
            double[] cv = perScenario.stream().filter(ScenarioEvaluation::hasExplanationScore)
                    .mapToDouble(ScenarioEvaluation::getCoverage).toArray();
            double[] cn = perScenario.stream().filter(ScenarioEvaluation::hasExplanationScore)
                    .mapToDouble(ScenarioEvaluation::getConciseness).toArray();
            double[] sg = perScenario.stream().filter(ScenarioEvaluation::hasExplanationScore)
                    .mapToDouble(ScenarioEvaluation::getSemanticGroundedness).toArray();
            double[] ov = perScenario.stream().filter(ScenarioEvaluation::hasExplanationScore)
                    .mapToDouble(ScenarioEvaluation::getOverallExplanationScore).toArray();
            agg.meanFaithfulness(mean(f))
               .meanCoverage(mean(cv))
               .meanConciseness(mean(cn))
               .meanSemanticGroundedness(mean(sg))
               .meanOverallExplanationScore(mean(ov));
        }

        return agg.build();
    }

    // -----------------------------------------------------------------------
    // Statistical helpers
    // -----------------------------------------------------------------------

    static double mean(double[] values) {
        if (values.length == 0) return 0.0;
        double sum = 0;
        for (double v : values) sum += v;
        return sum / values.length;
    }

    /** Sample standard deviation (Bessel-corrected, n-1). */
    static double std(double[] values) {
        if (values.length <= 1) return 0.0;
        double m   = mean(values);
        double sum = 0;
        for (double v : values) sum += (v - m) * (v - m);
        return Math.sqrt(sum / (values.length - 1));
    }
}
