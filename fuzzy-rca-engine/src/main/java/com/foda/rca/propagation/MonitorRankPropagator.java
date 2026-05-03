package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * MonitorRank-style external baseline (Kim, Sumbaly, Shah, ACM SIGMETRICS 2013):
 * personalized random walk with restart on the service dependency graph,
 * starting from anomalous services, ranking root-cause candidates by
 * stationary distribution mass.
 *
 * <p>This propagator is a non-ablation external comparator for the FODA-12
 * benchmark; it is conceptually unrelated to the noisy-OR confidence model
 * used by FCP-RCA. It is a drop-in {@link ConfidencePropagator} so it can be
 * plugged into the existing benchmark harness without touching the rest of
 * the pipeline.</p>
 *
 * <h2>Algorithm</h2>
 * <ol>
 *   <li>Anomalous set A = { s : H(s) > {@value #ANOMALY_THRESHOLD} }.</li>
 *   <li>Transition matrix: from s, walk to t in callees(s) (=
 *       {@code graph.getOutgoingEdges(s)}) with probability proportional to
 *       w(s,t). Services with no callees self-loop.</li>
 *   <li>Restart vector r: probability mass on A only, proportional to H(s).
 *       If A is empty, fall back to uniform over all services.</li>
 *   <li>Power iteration:
 *       π_{k+1} = (1 − α) · π_k · P + α · r,  with α = {@value #DEFAULT_RESTART_PROB}.</li>
 *   <li>Stop when ||π_{k+1} − π_k||_∞ ≤ ε ({@value #DEFAULT_EPSILON}) or
 *       k ≥ {@value #DEFAULT_MAX_ITERATIONS}.</li>
 *   <li>Output π_∞ as a probability distribution that sums to 1.</li>
 * </ol>
 *
 * <h2>Walk direction</h2>
 * <p>The graph stores edges as caller→callee (s→t means s calls t). For each
 * service s the influence-set in {@link IterativeConfidencePropagator} is
 * {@code getOutgoingEdges(s)} — i.e., s's callees. The walker matches that
 * convention: from s it transitions to t ∈ callees(s) along graph-stored edges,
 * weighted by w(s,t). This places stationary mass on services that many other
 * services depend on (typical root-cause hubs), in the same direction the
 * iterative propagator's value flow originates from.</p>
 *
 * <h2>Score scale</h2>
 * <p>Output scores form a probability distribution over services (sum = 1),
 * so absolute values depend on |V|. When fed into the standard
 * {@code TopKCauseRanker} (threshold 0.10), services with mass below 0.10 are
 * filtered out — this is a real characteristic of MonitorRank under the
 * existing benchmark configuration, not a bug.</p>
 */
@Slf4j
public class MonitorRankPropagator implements ConfidencePropagator {

    public static final double ANOMALY_THRESHOLD       = 0.30;
    public static final double DEFAULT_RESTART_PROB    = 0.15;
    public static final double DEFAULT_EPSILON         = 1e-6;
    public static final int    DEFAULT_MAX_ITERATIONS  = 100;

    @Getter private final double anomalyThreshold;
    @Getter private final double restartProbability;
    @Getter private final double epsilon;
    @Getter private final int    maxIterations;

    public MonitorRankPropagator() {
        this(ANOMALY_THRESHOLD, DEFAULT_RESTART_PROB, DEFAULT_EPSILON, DEFAULT_MAX_ITERATIONS);
    }

    public MonitorRankPropagator(double anomalyThreshold,
                                  double restartProbability,
                                  double epsilon,
                                  int maxIterations) {
        if (anomalyThreshold < 0.0 || anomalyThreshold >= 1.0)
            throw new IllegalArgumentException("anomalyThreshold must be in [0, 1)");
        if (restartProbability <= 0.0 || restartProbability >= 1.0)
            throw new IllegalArgumentException("restartProbability must be in (0, 1)");
        if (epsilon <= 0)
            throw new IllegalArgumentException("epsilon must be > 0");
        if (maxIterations < 1)
            throw new IllegalArgumentException("maxIterations must be >= 1");
        this.anomalyThreshold   = anomalyThreshold;
        this.restartProbability = restartProbability;
        this.epsilon            = epsilon;
        this.maxIterations      = maxIterations;
    }

    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        List<String> services = new ArrayList<>(graph.getServices());
        int n = services.size();
        Map<String, Integer> idx = new LinkedHashMap<>();
        for (int i = 0; i < n; i++) idx.put(services.get(i), i);

        if (n == 0) return Collections.emptyMap();
        if (n == 1) return Collections.singletonMap(services.get(0), 1.0);

        // ----- H(s) -----
        double[] H = new double[n];
        for (int i = 0; i < n; i++) {
            FaultHypothesis h = hypotheses.get(services.get(i));
            H[i] = (h == null) ? 0.0 : h.getLocalConfidence();
        }

        // ----- Anomalous set A -----
        List<Integer> anomalous = new ArrayList<>();
        for (int i = 0; i < n; i++) if (H[i] > anomalyThreshold) anomalous.add(i);

        // ----- Restart vector r -----
        double[] r = new double[n];
        if (anomalous.isEmpty()) {
            // Fall back: uniform over all services. With no anomaly signal there is
            // no meaningful restart distribution; return uniform stationary state.
            log.debug("MonitorRank: empty anomalous set — falling back to uniform distribution");
            double u = 1.0 / n;
            Map<String, Double> uniform = new LinkedHashMap<>();
            for (String s : services) uniform.put(s, u);
            return Collections.unmodifiableMap(uniform);
        } else {
            double sumH = 0.0;
            for (int i : anomalous) sumH += H[i];
            if (sumH <= 0.0) {
                double u = 1.0 / anomalous.size();
                for (int i : anomalous) r[i] = u;
            } else {
                for (int i : anomalous) r[i] = H[i] / sumH;
            }
        }

        // ----- Transition matrix rows: row i = transitions from service i -----
        // P[i][j] = prob of stepping from i to j
        double[][] P = new double[n][n];
        for (int i = 0; i < n; i++) {
            String s = services.get(i);
            List<Edge> callees = graph.getOutgoingEdges(s);
            if (callees.isEmpty()) {
                P[i][i] = 1.0;     // self-loop for nodes with no callees
                continue;
            }
            double rowSum = 0.0;
            for (Edge e : callees) rowSum += e.getWeight();
            if (rowSum <= 0.0) {
                P[i][i] = 1.0;
                continue;
            }
            for (Edge e : callees) {
                Integer j = idx.get(e.getTarget());
                if (j == null) continue;       // defensive: edge target outside V
                P[i][j] += e.getWeight() / rowSum;
            }
        }

        // ----- Initial π_0: uniform over A -----
        double[] pi = new double[n];
        double init = 1.0 / anomalous.size();
        for (int i : anomalous) pi[i] = init;

        // ----- Power iteration -----
        double[] next = new double[n];
        int iter = 0;
        double residual = Double.MAX_VALUE;
        double oneMinusAlpha = 1.0 - restartProbability;

        while (residual > epsilon && iter < maxIterations) {
            // next = (1-α) · π · P + α · r
            for (int j = 0; j < n; j++) next[j] = restartProbability * r[j];
            for (int i = 0; i < n; i++) {
                double pi_i = pi[i];
                if (pi_i == 0.0) continue;
                double[] row = P[i];
                for (int j = 0; j < n; j++) {
                    if (row[j] != 0.0) next[j] += oneMinusAlpha * pi_i * row[j];
                }
            }

            residual = 0.0;
            for (int j = 0; j < n; j++) {
                double d = Math.abs(next[j] - pi[j]);
                if (d > residual) residual = d;
                pi[j] = next[j];
            }
            iter++;
        }

        // Numerical guard: re-normalize so π sums to exactly 1.
        double total = 0.0;
        for (int j = 0; j < n; j++) total += pi[j];
        if (total > 0.0) {
            for (int j = 0; j < n; j++) pi[j] /= total;
        }

        if (residual > epsilon) {
            log.warn("MonitorRank: did not fully converge after {} iterations (Δ = {}).",
                     maxIterations, residual);
        } else {
            log.debug("MonitorRank: converged after {} iteration(s) (Δ = {})", iter, residual);
        }

        Map<String, Double> out = new LinkedHashMap<>();
        for (int i = 0; i < n; i++) out.put(services.get(i), pi[i]);
        return Collections.unmodifiableMap(out);
    }
}
