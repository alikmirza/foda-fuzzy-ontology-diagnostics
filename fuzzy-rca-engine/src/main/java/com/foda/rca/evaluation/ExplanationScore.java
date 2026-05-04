package com.foda.rca.evaluation;

import lombok.Builder;
import lombok.Value;

/**
 * Per-explanation quality score produced by {@link ExplanationQualityMetric}.
 *
 * <p>All four sub-scores are in [0, 1]; {@link #overall} is their unweighted
 * arithmetic mean. The components are intended to be conceptually orthogonal
 * (faithfulness ≠ coverage ≠ conciseness ≠ semantic groundedness), and we
 * deliberately avoid weighting absent empirical justification — see the
 * "Aggregation policy" section of {@link ExplanationQualityMetric}.</p>
 *
 * <p>{@link #toString()} renders all five values to 4 decimal places in a
 * compact CSV-friendly form so individual scores can be logged inline without
 * triggering CSV-quoting concerns at the writer side.</p>
 */
@Value
@Builder
public class ExplanationScore {

    /** Faithfulness ∈ [0,1]: does the explanation reference the ground-truth root cause(s)? */
    double faithfulness;

    /** Coverage ∈ [0,1]: does the rendered causal path match the ground-truth path? */
    double coverage;

    /** Conciseness ∈ [0,1]: 1 − fraction of non-stop-word tokens that repeat &gt; 2 times. */
    double conciseness;

    /** SemanticGroundedness ∈ [0,1]: fraction of technical entities backed by an OWL IRI. */
    double semanticGroundedness;

    /** Overall ∈ [0,1]: unweighted mean of the four sub-scores. */
    double overall;

    /**
     * Compact 5-tuple representation suitable for inline logging or CSV ingestion:
     * {@code F=0.5000 C=1.0000 N=0.9000 G=0.2500 O=0.6625}.
     */
    @Override
    public String toString() {
        return String.format(
                "F=%.4f C=%.4f N=%.4f G=%.4f O=%.4f",
                faithfulness, coverage, conciseness, semanticGroundedness, overall);
    }
}
