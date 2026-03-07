package com.foda.rca.fuzzification;

import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.ServiceMetrics;
import lombok.extern.slf4j.Slf4j;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Default implementation of {@link FaultFuzzifier} using trapezoidal and triangular
 * membership functions calibrated for microservice SLO thresholds.
 *
 * <h2>Fuzzification Universe (Section 3.1)</h2>
 *
 * <h3>CPU Usage (%)</h3>
 * <pre>
 *  LOW      : trap(0, 0, 30, 50)   – below 30 % fully LOW, fades at 50 %
 *  MEDIUM   : tri(30, 55, 80)      – peaks at 55 %, symmetric slopes
 *  HIGH     : trap(65, 85, 100, 100) – rises from 65 %, fully HIGH above 85 %
 * </pre>
 *
 * <h3>Latency (ms)</h3>
 * <pre>
 *  NORMAL   : trap(0, 0, 80, 150)
 *  ELEVATED : tri(80, 250, 500)
 *  CRITICAL : trap(400, 600, ∞, ∞)  (modelled as trap(400, 600, 1e9, 1e9))
 * </pre>
 *
 * <h3>Memory Usage (%)</h3>
 * <pre>
 *  LOW      : trap(0, 0, 40, 60)
 *  MEDIUM   : tri(40, 65, 85)
 *  HIGH     : trap(75, 90, 100, 100)
 * </pre>
 *
 * <h3>Error Rate (fraction in [0, 1])</h3>
 * <pre>
 *  NONE     : trap(0, 0, 0.005, 0.01)
 *  LOW      : tri(0.005, 0.02, 0.05)
 *  ELEVATED : tri(0.04, 0.07, 0.12)
 *  HIGH     : trap(0.10, 0.15, 1.0, 1.0)
 * </pre>
 *
 * <h3>Throughput (req/s) — relative to a configurable baseline</h3>
 * <pre>
 *  LOW      : trap(0, 0, tLow, tNormal)   where tLow = baseline*0.3, tNormal = baseline*0.6
 *  NORMAL   : trap(tNormal, baseline, ∞, ∞)
 * </pre>
 *
 * <p>Label convention: {@code "<metric>_<TERM>"}, e.g. {@code "cpu_HIGH"},
 * {@code "latency_CRITICAL"}, {@code "errorRate_ELEVATED"}.</p>
 */
@Slf4j
public class FaultFuzzifierImpl implements FaultFuzzifier {

    // -----------------------------------------------------------------------
    // CPU membership functions
    // -----------------------------------------------------------------------
    private static final MembershipFunction CPU_LOW    = new TrapezoidalMF(0, 0, 30, 50);
    private static final MembershipFunction CPU_MEDIUM = new TriangularMF(30, 55, 80);
    private static final MembershipFunction CPU_HIGH   = new TrapezoidalMF(65, 85, 100, 100);

    // -----------------------------------------------------------------------
    // Latency membership functions (ms)
    // -----------------------------------------------------------------------
    private static final MembershipFunction LAT_NORMAL   = new TrapezoidalMF(0, 0, 80, 150);
    private static final MembershipFunction LAT_ELEVATED = new TriangularMF(80, 250, 500);
    private static final MembershipFunction LAT_CRITICAL = new TrapezoidalMF(400, 600, 1e9, 1e9);

    // -----------------------------------------------------------------------
    // Memory membership functions
    // -----------------------------------------------------------------------
    private static final MembershipFunction MEM_LOW    = new TrapezoidalMF(0, 0, 40, 60);
    private static final MembershipFunction MEM_MEDIUM = new TriangularMF(40, 65, 85);
    private static final MembershipFunction MEM_HIGH   = new TrapezoidalMF(75, 90, 100, 100);

    // -----------------------------------------------------------------------
    // Error-rate membership functions (fraction in [0, 1])
    // -----------------------------------------------------------------------
    private static final MembershipFunction ERR_NONE     = new TrapezoidalMF(0, 0, 0.005, 0.01);
    private static final MembershipFunction ERR_LOW      = new TriangularMF(0.005, 0.02, 0.05);
    private static final MembershipFunction ERR_ELEVATED = new TriangularMF(0.04, 0.07, 0.12);
    private static final MembershipFunction ERR_HIGH     = new TrapezoidalMF(0.10, 0.15, 1.0, 1.0);

    /**
     * Nominal throughput baseline used to calibrate relative LOW/NORMAL sets.
     * Default: 1000 req/s; override via constructor for environment-specific tuning.
     */
    private final double throughputBaseline;

    private final MembershipFunction throughputLow;
    private final MembershipFunction throughputNormal;

    /** Creates a fuzzifier with a default throughput baseline of 1000 req/s. */
    public FaultFuzzifierImpl() {
        this(1000.0);
    }

    /**
     * Creates a fuzzifier with a custom throughput baseline.
     *
     * @param throughputBaseline expected peak throughput for "NORMAL" classification (req/s)
     */
    public FaultFuzzifierImpl(double throughputBaseline) {
        if (throughputBaseline <= 0) throw new IllegalArgumentException("Baseline must be > 0");
        this.throughputBaseline = throughputBaseline;
        double tLow    = throughputBaseline * 0.3;
        double tNormal = throughputBaseline * 0.6;
        this.throughputLow    = new TrapezoidalMF(0, 0, tLow, tNormal);
        this.throughputNormal = new TrapezoidalMF(tNormal, throughputBaseline, 1e9, 1e9);
    }

    /**
     * {@inheritDoc}
     *
     * <p>All five metric dimensions are evaluated independently.  Each crisp measurement is
     * mapped to membership degrees via the calibrated membership functions above.  The
     * resulting key-value pairs are assembled into an immutable {@link FuzzyVector}.</p>
     */
    @Override
    public FuzzyVector fuzzify(ServiceMetrics metrics) {
        Objects.requireNonNull(metrics, "metrics must not be null");
        log.debug("Fuzzifying metrics for service '{}'", metrics.getServiceId());

        Map<String, Double> m = new LinkedHashMap<>();

        // CPU
        m.put("cpu_LOW",    CPU_LOW.evaluate(metrics.getCpuUsage()));
        m.put("cpu_MEDIUM", CPU_MEDIUM.evaluate(metrics.getCpuUsage()));
        m.put("cpu_HIGH",   CPU_HIGH.evaluate(metrics.getCpuUsage()));

        // Latency
        m.put("latency_NORMAL",   LAT_NORMAL.evaluate(metrics.getLatencyMs()));
        m.put("latency_ELEVATED", LAT_ELEVATED.evaluate(metrics.getLatencyMs()));
        m.put("latency_CRITICAL", LAT_CRITICAL.evaluate(metrics.getLatencyMs()));

        // Memory
        m.put("memory_LOW",    MEM_LOW.evaluate(metrics.getMemoryUsage()));
        m.put("memory_MEDIUM", MEM_MEDIUM.evaluate(metrics.getMemoryUsage()));
        m.put("memory_HIGH",   MEM_HIGH.evaluate(metrics.getMemoryUsage()));

        // Error rate
        m.put("errorRate_NONE",     ERR_NONE.evaluate(metrics.getErrorRate()));
        m.put("errorRate_LOW",      ERR_LOW.evaluate(metrics.getErrorRate()));
        m.put("errorRate_ELEVATED", ERR_ELEVATED.evaluate(metrics.getErrorRate()));
        m.put("errorRate_HIGH",     ERR_HIGH.evaluate(metrics.getErrorRate()));

        // Throughput
        m.put("throughput_LOW",    throughputLow.evaluate(metrics.getThroughput()));
        m.put("throughput_NORMAL", throughputNormal.evaluate(metrics.getThroughput()));

        log.debug("Fuzzy vector for '{}': {}", metrics.getServiceId(), m);

        return FuzzyVector.builder()
                .serviceId(metrics.getServiceId())
                .memberships(m)
                .build();
    }
}
