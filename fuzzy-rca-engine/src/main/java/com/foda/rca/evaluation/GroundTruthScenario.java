package com.foda.rca.evaluation;

import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceMetrics;
import lombok.Builder;
import lombok.Value;

import java.util.List;
import java.util.Set;

/**
 * A labelled fault injection scenario used for experimental evaluation (Section 5.1).
 *
 * <p>Each scenario encodes a controlled experiment where one or more services have been
 * injected with a known fault type (e.g. CPU saturation, memory pressure). The
 * {@link #trueRootCauses} set provides the ground-truth labels used to compute
 * Precision@k, Recall@k, MRR, and NDCG in {@link RcaEvaluator}.</p>
 *
 * <h2>Scenario design principles (Section 5.1)</h2>
 * <ul>
 *   <li>Each scenario simulates one injected fault affecting exactly the services in
 *       {@link #trueRootCauses}.</li>
 *   <li>The metric observations reflect both the injected fault (elevated metrics at the
 *       root-cause service) and residual propagation effects (mild elevation at callers).</li>
 *   <li>The graph topology can be shared across scenarios to isolate the effect of
 *       different fault types on the same architecture.</li>
 * </ul>
 */
@Value
@Builder
public class GroundTruthScenario {

    /** Unique identifier for reproducibility and cross-referencing with paper Table 3. */
    String scenarioId;

    /** Human-readable name (e.g. "DB_CRITICAL_LATENCY", "GATEWAY_CPU_SATURATION"). */
    String scenarioName;

    /** Short description of the injected fault condition. */
    String description;

    /**
     * Injected fault type label used in the paper's scenario taxonomy (Table 3).
     * One of: CPU_SATURATION, MEMORY_PRESSURE, SERVICE_ERROR, LATENCY_ANOMALY,
     * CASCADING_FAILURE, RESOURCE_CONTENTION.
     */
    String faultType;

    /** Per-service metric observations (one entry per service). */
    List<ServiceMetrics> observations;

    /** Weighted directed dependency graph for this scenario. */
    ServiceDependencyGraph dependencyGraph;

    /**
     * Ground-truth root cause(s). Typically one service, but cascading scenarios
     * may have two co-root-causes (e.g. a misconfigured dependency causing two services
     * to fail simultaneously).
     */
    Set<String> trueRootCauses;
}
