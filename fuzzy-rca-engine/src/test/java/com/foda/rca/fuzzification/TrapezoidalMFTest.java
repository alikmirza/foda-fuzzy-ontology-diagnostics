package com.foda.rca.fuzzification;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link TrapezoidalMF} and {@link TriangularMF}.
 * Covers boundary conditions, slopes, and degeneracy to trapezoidal.
 */
@DisplayName("Membership Function Tests")
class TrapezoidalMFTest {

    // -----------------------------------------------------------------------
    // TrapezoidalMF correctness
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("μ(x < a) = 0 (left-of-support)")
    void leftOfSupport_isZero() {
        TrapezoidalMF mf = new TrapezoidalMF(20, 40, 60, 80);
        assertEquals(0.0, mf.evaluate(10), 1e-9);
        assertEquals(0.0, mf.evaluate(20), 1e-9);  // x == a → still 0 (open left)
    }

    @Test
    @DisplayName("μ(x > d) = 0 (right-of-support)")
    void rightOfSupport_isZero() {
        TrapezoidalMF mf = new TrapezoidalMF(20, 40, 60, 80);
        assertEquals(0.0, mf.evaluate(90), 1e-9);
        assertEquals(0.0, mf.evaluate(80), 1e-9);  // x == d → still 0 (open right)
    }

    @Test
    @DisplayName("μ(x in [b,c]) = 1 (flat top)")
    void flatTop_isOne() {
        TrapezoidalMF mf = new TrapezoidalMF(20, 40, 60, 80);
        assertEquals(1.0, mf.evaluate(40), 1e-9);
        assertEquals(1.0, mf.evaluate(50), 1e-9);
        assertEquals(1.0, mf.evaluate(60), 1e-9);
    }

    @ParameterizedTest(name = "x={0} → μ={1}")
    @CsvSource({
        "30, 0.5",  // midpoint of rising slope [20,40]
        "70, 0.5",  // midpoint of falling slope [60,80]
        "25, 0.25", // quarter up on rising slope
        "75, 0.25"  // quarter down on falling slope
    })
    @DisplayName("Slope interpolation")
    void slopeInterpolation(double x, double expected) {
        TrapezoidalMF mf = new TrapezoidalMF(20, 40, 60, 80);
        assertEquals(expected, mf.evaluate(x), 1e-9);
    }

    @Test
    @DisplayName("Constructor rejects a > b ordering")
    void constructor_rejectsInvalidOrder() {
        assertThrows(IllegalArgumentException.class,
            () -> new TrapezoidalMF(50, 30, 60, 80));
    }

    @Test
    @DisplayName("Open-right trapezoid: μ(x >= b) = 1 for very large x")
    void openRight_alwaysOne() {
        TrapezoidalMF mf = new TrapezoidalMF(400, 600, 1e9, 1e9);
        assertEquals(1.0, mf.evaluate(700),   1e-9);
        assertEquals(1.0, mf.evaluate(100000), 1e-9);
        assertEquals(0.0, mf.evaluate(300),   1e-9);
    }

    // -----------------------------------------------------------------------
    // TriangularMF correctness
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Triangle: μ(peak) = 1")
    void triangular_peakIsOne() {
        TriangularMF mf = new TriangularMF(10, 50, 90);
        assertEquals(1.0, mf.evaluate(50), 1e-9);
    }

    @Test
    @DisplayName("Triangle: μ(a) = μ(c) = 0")
    void triangular_feetAreZero() {
        TriangularMF mf = new TriangularMF(10, 50, 90);
        assertEquals(0.0, mf.evaluate(10), 1e-9);
        assertEquals(0.0, mf.evaluate(90), 1e-9);
    }

    @Test
    @DisplayName("Triangle: mid-slopes are 0.5")
    void triangular_midSlopeIsHalf() {
        TriangularMF mf = new TriangularMF(10, 50, 90);
        assertEquals(0.5, mf.evaluate(30), 1e-9);  // (30-10)/(50-10) = 0.5
        assertEquals(0.5, mf.evaluate(70), 1e-9);  // (90-70)/(90-50) = 0.5
    }

    // -----------------------------------------------------------------------
    // Return value range guarantee
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("All MF values are in [0, 1] for arbitrary inputs")
    void valueAlwaysInUnitInterval() {
        TrapezoidalMF mf = new TrapezoidalMF(30, 50, 70, 90);
        for (double x = -10; x <= 110; x += 0.7) {
            double mu = mf.evaluate(x);
            assertTrue(mu >= 0.0 && mu <= 1.0,
                "μ(" + x + ")=" + mu + " is outside [0,1]");
        }
    }
}
