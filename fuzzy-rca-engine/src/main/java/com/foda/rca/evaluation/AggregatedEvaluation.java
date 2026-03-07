package com.foda.rca.evaluation;

import lombok.Builder;
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
     */
    public static String csvHeader() {
        return "algorithm,k,n_scenarios,"
             + "mean_precision,std_precision,"
             + "mean_recall,std_recall,"
             + "mean_mrr,std_mrr,"
             + "mean_ndcg,std_ndcg,"
             + "top1_accuracy";
    }

    /**
     * Returns a CSV data row for this evaluation result.
     *
     * <p>Column order matches {@link #csvHeader()}. Numeric fields are formatted with
     * 6 decimal places to preserve full precision for downstream statistical analysis.</p>
     */
    public String toCsvRow() {
        return String.format("%s,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f",
            algorithmName, k, numScenarios,
            meanPrecisionAtK, stdPrecisionAtK,
            meanRecallAtK,    stdRecallAtK,
            meanMrr,          stdMrr,
            meanNdcgAtK,      stdNdcgAtK,
            top1Accuracy);
    }
}
