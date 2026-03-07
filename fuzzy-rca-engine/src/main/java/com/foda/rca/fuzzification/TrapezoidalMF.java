package com.foda.rca.fuzzification;

/**
 * Trapezoidal membership function (the most general piecewise-linear fuzzy set).
 *
 * <p>Defined by four parameters a ≤ b ≤ c ≤ d that control the shape:</p>
 * <pre>
 *          ____
 *         /    \
 *        /      \
 * ------/        \------
 *      a  b    c  d
 *
 *      ⎧ 0,               x < a
 *      ⎪ (x – a)/(b – a), a ≤ x < b   (rising slope)
 * μ =  ⎨ 1,               b ≤ x ≤ c   (flat top)
 *      ⎪ (d – x)/(d – c), c < x ≤ d   (falling slope)
 *      ⎩ 0,               x > d
 * </pre>
 *
 * <p>When b == c the function degenerates to a triangle.  When a == b the left
 * slope is a step (open at the left); when c == d the right slope is a step
 * (open at the right), useful for modelling "very high" sets that extend to +∞.</p>
 *
 * <p>Reference: Zadeh (1965), Mendel (2001) <em>Uncertain Rule-Based Fuzzy Logic
 * Systems</em>, Eq. 2.1.</p>
 */
public final class TrapezoidalMF implements MembershipFunction {

    private final double a, b, c, d;

    /**
     * Constructs a trapezoidal membership function.
     *
     * @param a left foot (membership begins rising)
     * @param b left shoulder (membership reaches 1)
     * @param c right shoulder (membership starts falling)
     * @param d right foot (membership reaches 0)
     * @throws IllegalArgumentException if a &gt; b, b &gt; c, or c &gt; d
     */
    public TrapezoidalMF(double a, double b, double c, double d) {
        if (a > b || b > c || c > d) {
            throw new IllegalArgumentException(
                String.format("Trapezoidal MF requires a≤b≤c≤d, got: [%f, %f, %f, %f]", a, b, c, d));
        }
        this.a = a; this.b = b; this.c = c; this.d = d;
    }

    /** {@inheritDoc} */
    @Override
    public double evaluate(double x) {
        if (x <= a || x >= d) return 0.0;
        if (x >= b && x <= c) return 1.0;
        if (x < b)  return (x - a) / (b - a);   // rising slope
        return (d - x) / (d - c);                // falling slope
    }

    @Override
    public String toString() {
        return String.format("TrapezoidalMF[%.2f, %.2f, %.2f, %.2f]", a, b, c, d);
    }
}
