package com.foda.rca.fuzzification;

/**
 * Functional interface representing a fuzzy membership function μ : ℝ → [0, 1].
 *
 * <p>Membership functions map a crisp input value {@code x} to the degree to which
 * {@code x} belongs to a fuzzy linguistic set (e.g., "CPU is HIGH").  Two canonical
 * shapes are provided: {@link TrapezoidalMF} and {@link TriangularMF}.</p>
 *
 * <p>All implementations must guarantee μ(x) ∈ [0, 1] for any finite {@code x}.</p>
 */
@FunctionalInterface
public interface MembershipFunction {

    /**
     * Evaluate the membership degree of the crisp value {@code x}.
     *
     * @param x the crisp observation (any finite double)
     * @return μ(x) ∈ [0, 1]
     */
    double evaluate(double x);
}
