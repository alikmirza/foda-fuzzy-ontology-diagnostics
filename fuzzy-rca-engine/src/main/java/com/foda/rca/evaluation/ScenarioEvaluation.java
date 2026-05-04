package com.foda.rca.evaluation;

import lombok.Builder;
import lombok.Builder.Default;
import lombok.Value;

import java.util.List;
import java.util.Set;

/**
 * Evaluation metrics for a single algorithm–scenario pair.
 *
 * <p>Stores the four standard IR/recommendation metrics used in RCA evaluation
 * (Section 5.2, Equations 6–9):</p>
 *
 * <table border="1">
 *   <tr><th>Metric</th><th>Formula</th><th>Interpretation</th></tr>
 *   <tr><td>Precision@k</td>
 *       <td>|top_k ∩ R| / k</td>
 *       <td>Fraction of returned causes that are true root causes</td></tr>
 *   <tr><td>Recall@k</td>
 *       <td>|top_k ∩ R| / |R|</td>
 *       <td>Fraction of true root causes recovered in top-k</td></tr>
 *   <tr><td>MRR</td>
 *       <td>1 / rank(first true cause)</td>
 *       <td>Quality of the single best prediction; MRR=1 means top-1 is correct</td></tr>
 *   <tr><td>NDCG@k</td>
 *       <td>DCG@k / IDCG@k</td>
 *       <td>Position-discounted ranking quality; rewards early placement of true causes</td></tr>
 * </table>
 *
 * where R = set of true root causes.
 */
@Value
@Builder
public class ScenarioEvaluation {

    /** Scenario identifier. */
    String scenarioId;

    /** Scenario display name. */
    String scenarioName;

    /** Algorithm name (e.g. "FCP-RCA", "LocalOnly"). */
    String algorithmName;

    /** Value of k used for @k metrics. */
    int k;

    // ── Core metrics ─────────────────────────────────────────────────────

    /**
     * Precision@k = |top_k ∩ R| / k  ∈ [0, 1].
     * Note: when |top_k| &lt; k (fewer candidates than k), we divide by |top_k|.
     */
    double precisionAtK;

    /**
     * Recall@k = |top_k ∩ R| / |R|  ∈ [0, 1].
     */
    double recallAtK;

    /**
     * Mean Reciprocal Rank = 1 / rank(first r ∈ R in ranked list).
     * MRR = 0 if no true root cause appears in the ranked list.
     */
    double mrr;

    /**
     * Normalised Discounted Cumulative Gain at k.
     * <pre>
     *   DCG@k  = ∑_{i=1}^{k} rel_i / log2(i+1)    where rel_i ∈ {0,1}
     *   IDCG@k = ∑_{i=1}^{min(k,|R|)} 1 / log2(i+1)
     *   NDCG@k = DCG@k / IDCG@k
     * </pre>
     */
    double ndcgAtK;

    // ── Evidence ─────────────────────────────────────────────────────────

    /** Predicted root causes (top-k ranked list), ordered by confidence. */
    List<String> predictedCauses;

    /** Ground-truth root cause set. */
    Set<String> trueRootCauses;

    /** True if predictedCauses.get(0) equals the sole (or primary) true root cause. */
    boolean topOneCorrect;

    /** Fault category of the injected fault for stratified analysis. */
    String faultType;

    // ── Explanation-quality metrics (optional; populated when RcaEvaluator
    //    is constructed with a non-null ExplanationQualityMetric). All four
    //    sub-scores and the overall are in [0,1]; default NaN signals "not
    //    computed" so downstream aggregation can skip rather than treat
    //    a missing score as a real zero.
    // ────────────────────────────────────────────────────────────────────
    @Default double faithfulness         = Double.NaN;
    @Default double coverage             = Double.NaN;
    @Default double conciseness          = Double.NaN;
    @Default double semanticGroundedness = Double.NaN;
    @Default double overallExplanationScore = Double.NaN;

    /** True when this scenario carries an explanation score (i.e. {@link #overallExplanationScore} is finite). */
    public boolean hasExplanationScore() {
        return !Double.isNaN(overallExplanationScore);
    }
}
