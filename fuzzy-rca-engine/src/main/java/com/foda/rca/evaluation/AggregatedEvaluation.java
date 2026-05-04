package com.foda.rca.evaluation;

import lombok.Builder;
import lombok.Builder.Default;
import lombok.Value;

import java.util.List;
import java.util.Map;

/**
 * Aggregated evaluation metrics across all scenarios for one algorithm.
 *
 * <p>This is the data object that populates Table 4 of the paper (comparison across
 * algorithms). For each metric the mean and sample standard deviation are reported
 * across all evaluation scenarios, enabling statistical comparison.</p>
 *
 * <p>The {@link #perScenarioResults} list provides the raw per-scenario data for
 * statistical tests (Wilcoxon signed-rank, paired t-test) and for the per-fault-type
 * stratified analysis (Table 5).</p>
 */
@Value
@Builder
public class AggregatedEvaluation {

    /** Algorithm identifier as it appears in the paper (e.g. "FCP-RCA", "LocalOnly"). */
    String algorithmName;

    /** Value of k used for all @k metrics. */
    int k;

    /** Number of scenarios evaluated. */
    int numScenarios;

    // ── Precision@k ──────────────────────────────────────────────────────
    double meanPrecisionAtK;
    double stdPrecisionAtK;

    // ── Recall@k ─────────────────────────────────────────────────────────
    double meanRecallAtK;
    double stdRecallAtK;

    // ── MRR ──────────────────────────────────────────────────────────────
    double meanMrr;
    double stdMrr;

    // ── NDCG@k ───────────────────────────────────────────────────────────
    double meanNdcgAtK;
    double stdNdcgAtK;

    /** Fraction of scenarios where the top-1 prediction is a true root cause. */
    double top1Accuracy;

    /** Per-fault-type breakdown: faultType → mean NDCG@k. */
    Map<String, Double> ndcgByFaultType;

    /** Raw per-scenario results for statistical significance testing. */
    List<ScenarioEvaluation> perScenarioResults;

    // ── Explanation-quality aggregates (optional; finite values only when
    //    RcaEvaluator was constructed with a non-null ExplanationQualityMetric).
    //    Default NaN signals "not computed" and renders as the empty string in CSV.
    // ────────────────────────────────────────────────────────────────────
    @Default double meanFaithfulness         = Double.NaN;
    @Default double meanCoverage             = Double.NaN;
    @Default double meanConciseness          = Double.NaN;
    @Default double meanSemanticGroundedness = Double.NaN;
    @Default double meanOverallExplanationScore = Double.NaN;

    /** True when explanation-quality aggregates were populated. */
    public boolean hasExplanationScores() {
        return !Double.isNaN(meanOverallExplanationScore);
    }

    // -----------------------------------------------------------------------
    // Formatting helpers
    // -----------------------------------------------------------------------

    /**
     * Returns a compact one-line summary suitable for console logging.
     *
     * <pre>
     *   [FCP-RCA] P@3=0.82±0.12  R@3=0.78±0.15  MRR=0.85±0.10  NDCG@3=0.84±0.11  Top1=0.80
     * </pre>
     */
    public String toSummaryLine() {
        return String.format(
            "[%s] P@%d=%.3f±%.3f  R@%d=%.3f±%.3f  MRR=%.3f±%.3f  NDCG@%d=%.3f±%.3f  Top1=%.3f",
            algorithmName,
            k, meanPrecisionAtK, stdPrecisionAtK,
            k, meanRecallAtK,    stdRecallAtK,
            meanMrr, stdMrr,
            k, meanNdcgAtK,      stdNdcgAtK,
            top1Accuracy);
    }

    /**
     * Returns a LaTeX table row compatible with the paper template.
     *
     * <pre>
     *   FCP-RCA & 0.82 ± 0.12 & 0.78 ± 0.15 & 0.85 ± 0.10 & 0.84 ± 0.11 & 0.80 \\
     * </pre>
     */
    public String toLatexRow() {
        return String.format(
            "%s & %.3f$\\pm$%.3f & %.3f$\\pm$%.3f & %.3f$\\pm$%.3f "
                + "& %.3f$\\pm$%.3f & %.3f \\\\ \\hline",
            algorithmName,
            meanPrecisionAtK, stdPrecisionAtK,
            meanRecallAtK,    stdRecallAtK,
            meanMrr,          stdMrr,
            meanNdcgAtK,      stdNdcgAtK,
            top1Accuracy);
    }

    /**
     * Returns a CSV header line matching the columns produced by {@link #toCsvRow()}.
     *
     * <p>The five {@code mean_*} explanation columns are always present in the schema —
     * when explanation scoring was disabled (no metric passed to the evaluator) they
     * render as empty fields, preserving column-count parity with the header.</p>
     */
    public static String csvHeader() {
        return "algorithm,k,n_scenarios,"
             + "mean_precision,std_precision,"
             + "mean_recall,std_recall,"
             + "mean_mrr,std_mrr,"
             + "mean_ndcg,std_ndcg,"
             + "top1_accuracy,"
             + "mean_faithfulness,mean_coverage,mean_conciseness,"
             + "mean_semantic_groundedness,mean_overall_explanation_score";
    }

    /**
     * Returns a CSV data row for this evaluation result.
     *
     * <p>Column order matches {@link #csvHeader()}. Numeric fields are formatted with
     * 6 decimal places to preserve full precision for downstream statistical analysis.
     * Explanation-quality fields render as the empty string when not computed (NaN).</p>
     */
    public String toCsvRow() {
        return String.format("%s,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s",
            algorithmName, k, numScenarios,
            meanPrecisionAtK, stdPrecisionAtK,
            meanRecallAtK,    stdRecallAtK,
            meanMrr,          stdMrr,
            meanNdcgAtK,      stdNdcgAtK,
            top1Accuracy,
            fmt(meanFaithfulness),
            fmt(meanCoverage),
            fmt(meanConciseness),
            fmt(meanSemanticGroundedness),
            fmt(meanOverallExplanationScore));
    }

    /**
     * CSV-friendly numeric formatter: missing-by-design values render as the
     * literal {@code NaN} (which pandas / R / Excel all parse as floating-point NaN),
     * never as the empty string — preserving column-count parity even with the
     * default {@link String#split(String)} behaviour that strips trailing empties.
     */
    private static String fmt(double v) {
        return Double.isNaN(v) ? "NaN" : String.format("%.6f", v);
    }
}
