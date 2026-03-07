package com.foda.rca.inference;

import com.foda.rca.model.FuzzyVector;
import lombok.Builder;
import lombok.Value;

import java.util.List;
import java.util.Objects;

/**
 * An immutable Mamdani-style fuzzy IF-THEN rule.
 *
 * <p>Rule structure:
 * <pre>IF antecedent_1 AND antecedent_2 AND … THEN consequence (with certaintyFactor)</pre>
 * </p>
 *
 * <p>The <em>firing strength</em> (activation degree) of a rule is:
 * <pre>α = certaintyFactor × min{ μ(antecedent_i) : i = 1…n }</pre>
 * where μ(antecedent_i) is the membership degree of the i-th antecedent label
 * retrieved from the service's {@link FuzzyVector}.</p>
 *
 * <p>The min-aggregation of antecedents is the standard Mamdani conjunction operator.
 * Multiplication by {@code certaintyFactor} models rule-level epistemic uncertainty
 * (e.g. expert confidence in the rule's validity).</p>
 *
 * @see MamdaniFuzzyRuleEngine
 */
@Value
@Builder
public class FuzzyRule {

    /**
     * Human-readable label for logging and explanation output
     * (e.g. {@code "R1: IF cpu_HIGH AND latency_CRITICAL THEN CPU_SATURATION"}).
     */
    String label;

    /**
     * Ordered list of antecedent labels (keys in {@link FuzzyVector#getMemberships()}).
     * All antecedents are conjunctively combined (logical AND = min-operator).
     */
    List<String> antecedents;

    /**
     * Fault category asserted by the rule's consequent
     * (e.g. {@code "CPU_SATURATION"}, {@code "MEMORY_LEAK"}).
     */
    String consequentCategory;

    /**
     * A-priori certainty factor CF ∈ (0, 1] encoding expert confidence in this rule.
     * CF = 1.0 means unconditional trust; CF = 0.6 means moderate confidence.
     */
    double certaintyFactor;

    /**
     * Compute the Mamdani firing strength of this rule against the supplied fuzzy vector.
     *
     * <p>α = CF × min{ v.get(a) : a ∈ antecedents }</p>
     *
     * @param v the fuzzified service health vector
     * @return firing strength α ∈ [0, 1]
     */
    public double firingStrength(FuzzyVector v) {
        Objects.requireNonNull(v, "FuzzyVector must not be null");
        double minMembership = antecedents.stream()
                .mapToDouble(v::get)
                .min()
                .orElse(0.0);
        return certaintyFactor * minMembership;
    }
}
