package com.foda.rca.model;

import lombok.Builder;
import lombok.Value;

import java.util.List;

/**
 * Local fault hypothesis produced by the <em>Fault Inference Layer</em> (Section 3.2).
 *
 * <p>The Mamdani rule engine evaluates all applicable IF-THEN rules against the service's
 * {@link FuzzyVector} and aggregates their consequents into a single <em>local confidence</em>
 * score {@code H} ∈ [0, 1].  This score expresses how strongly the observed metric pattern
 * of <em>this</em> service, in isolation, suggests a fault at that service.</p>
 *
 * <p>The local hypothesis is subsequently combined with upstream propagated confidence during
 * the confidence propagation phase (Section 3.3).</p>
 */
@Value
@Builder
public class FaultHypothesis {

    /** Service for which this hypothesis was inferred. */
    String serviceId;

    /**
     * Aggregated local fault confidence H ∈ [0, 1].
     *
     * <p>Derived via max-aggregation of all fired rule strengths:
     * <pre>H = max{ α_r : r is a fired rule }</pre>
     * where α_r = min{ μ(antecedent_i) } is the Mamdani firing strength of rule r.</p>
     */
    double localConfidence;

    /** Dominant fault category inferred from the highest-firing rule. */
    String dominantFaultCategory;

    /** Human-readable labels of all rules that fired (α_r > 0). */
    List<String> firedRules;

    /**
     * Per-rule firing strengths for transparency; key = rule label, value = α_r ∈ [0, 1].
     */
    java.util.Map<String, Double> ruleFireStrengths;
}
