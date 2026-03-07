package com.foda.rca.api;

import com.foda.rca.model.DiagnosisResult;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceMetrics;

import java.util.List;

/**
 * Primary entry-point of the Fuzzy Confidence Propagation Root Cause Analysis engine
 * (FCP-RCA, Section 3 of the paper).
 *
 * <p>A single call to {@link #diagnose} executes the full five-phase pipeline:</p>
 * <ol>
 *   <li>Fuzzification of raw metric observations.</li>
 *   <li>Mamdani-style fuzzy fault inference per service.</li>
 *   <li>Weighted confidence propagation through the dependency graph (noisy-OR).</li>
 *   <li>Top-k ranking of root-cause candidates.</li>
 *   <li>Natural-language explanation generation.</li>
 * </ol>
 *
 * <p>Implementations must be <strong>thread-safe</strong>; a single engine instance
 * may be shared across concurrent diagnostic requests.</p>
 *
 * <p>The interface is intentionally minimal to facilitate mocking in unit tests and
 * to keep the public API stable across algorithm revisions.</p>
 */
public interface FuzzyRcaEngine {

    /**
     * Execute the FCP-RCA pipeline and return a ranked diagnosis.
     *
     * @param metricObservations list of per-service metric snapshots (one per service)
     * @param dependencyGraph    weighted directed call-dependency graph
     * @param topK               maximum number of root-cause candidates to return
     * @return a {@link DiagnosisResult} containing ranked causes, evidence, and explanations
     * @throws IllegalArgumentException if {@code metricObservations} is empty or {@code topK} ≤ 0
     */
    DiagnosisResult diagnose(List<ServiceMetrics> metricObservations,
                             ServiceDependencyGraph dependencyGraph,
                             int topK);
}
