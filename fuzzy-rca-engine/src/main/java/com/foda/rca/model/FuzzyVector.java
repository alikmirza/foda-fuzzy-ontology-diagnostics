package com.foda.rca.model;

import lombok.Builder;
import lombok.Value;

import java.util.Collections;
import java.util.Map;

/**
 * Fuzzified representation of a service's health state.
 *
 * <p>This is the output of the <em>Fuzzification Layer</em> (Section 3.1).  Each linguistic
 * variable (e.g. {@code cpu_HIGH}) maps to a membership degree μ ∈ [0, 1].  The full set of
 * memberships constitutes the antecedent universe used by the rule engine.</p>
 *
 * <p>Key: {@code "<metric>_<term>"}, e.g. {@code "cpu_HIGH"}, {@code "latency_CRITICAL"},
 * {@code "errorRate_ELEVATED"}.  Value: μ ∈ [0, 1].</p>
 */
@Value
@Builder
public class FuzzyVector {

    /** Service whose metrics have been fuzzified. */
    String serviceId;

    /**
     * Immutable map of linguistic-variable → membership degree.
     * Example entries: {@code "cpu_HIGH" → 0.82}, {@code "latency_CRITICAL" → 0.45}.
     */
    Map<String, Double> memberships;

    /**
     * Returns the membership degree for a given linguistic label,
     * or {@code 0.0} if the label is absent (closed-world assumption).
     */
    public double get(String label) {
        return memberships.getOrDefault(label, 0.0);
    }

    /** Returns an unmodifiable view of all membership entries. */
    public Map<String, Double> getMemberships() {
        return Collections.unmodifiableMap(memberships);
    }
}
