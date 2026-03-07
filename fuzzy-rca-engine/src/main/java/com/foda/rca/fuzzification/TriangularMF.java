package com.foda.rca.fuzzification;

/**
 * Triangular membership function — a special case of the trapezoidal MF where b == c.
 *
 * <pre>
 *        /\
 *       /  \
 * -----/    \-----
 *     a   b   c
 *
 *      ⎧ 0,               x ≤ a or x ≥ c
 * μ =  ⎨ (x – a)/(b – a), a < x ≤ b     (rising slope)
 *      ⎩ (c – x)/(c – b), b < x < c     (falling slope)
 * </pre>
 *
 * <p>Preferred for medium/normal linguistic terms where the membership peaks at a
 * single crisp value (the mode) and decays symmetrically or asymmetrically on
 * either side.</p>
 *
 * <p>Delegates to {@link TrapezoidalMF} with {@code b == c == peak}.</p>
 */
public final class TriangularMF implements MembershipFunction {

    private final TrapezoidalMF delegate;

    /**
     * Constructs a triangular membership function.
     *
     * @param a    left foot (μ rises from 0)
     * @param peak apex (μ = 1)
     * @param c    right foot (μ falls back to 0)
     * @throws IllegalArgumentException if a &gt; peak or peak &gt; c
     */
    public TriangularMF(double a, double peak, double c) {
        this.delegate = new TrapezoidalMF(a, peak, peak, c);
    }

    /** {@inheritDoc} */
    @Override
    public double evaluate(double x) {
        return delegate.evaluate(x);
    }

    @Override
    public String toString() {
        return delegate.toString().replace("Trapezoidal", "Triangular");
    }
}
