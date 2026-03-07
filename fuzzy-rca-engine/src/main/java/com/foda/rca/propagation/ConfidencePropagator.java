package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;

import java.util.Map;

/**
 * Confidence Propagation Layer interface (Section 3.3 of the FCP-RCA paper).
 *
 * <p>Propagates local fault hypotheses <strong>backward</strong> through the service
 * dependency graph {@code G = (S, E, W)} to compute a final aggregated confidence score
 * C(s) for each service.  The final score reflects both the service's own symptom evidence
 * and the fault signal propagated from its downstream callees (dependencies).</p>
 *
 * <h2>RCA Propagation Direction</h2>
 *
 * <p>An edge {@code s → t} means "s calls t". Because a fault at callee {@code t} causes
 * symptoms at caller {@code s}, confidence flows <em>backward</em> from callees to callers.
 * Services with no outgoing edges (leaves / standalone dependencies) are processed first,
 * and their confidence is accumulated by the services that call them.</p>
 *
 * <h2>Propagation Model: Probabilistic OR (Noisy-OR)</h2>
 *
 * <p>For service {@code s} with callee set {@code callees(s) = { t : s→t ∈ E }}:</p>
 * <pre>
 *   P(s) = 1 – ∏_{t ∈ callees(s)} (1 – C(t) × w(s,t))   [callee-dependency contribution]
 *   C(s) = 1 – (1 – H(s)) × (1 – P(s))                   [bounded sum of local + callee evidence]
 * </pre>
 *
 * <p>where {@code H(s)} is the local hypothesis confidence from the inference layer
 * and {@code w(s,t)} is the coupling strength of the call edge ({@code s} calls {@code t}).</p>
 *
 * <p>This model is equivalent to the noisy-OR gate from the Bayesian network literature,
 * adapted for the fuzzy confidence domain.  It satisfies:
 * <ul>
 *   <li><strong>Monotonicity:</strong> C(s) ≥ H(s) — callee evidence never reduces
 *       the caller's confidence.</li>
 *   <li><strong>Boundedness:</strong> C(s) ∈ [0, 1] for all s.</li>
 *   <li><strong>Fault-source priority:</strong> The service with the highest local H(s)
 *       will dominate its callers after propagation (assuming calibrated weights).</li>
 * </ul>
 * </p>
 */
public interface ConfidencePropagator {

    /**
     * Propagate local fault confidences through the dependency graph.
     *
     * @param hypotheses    local fault hypothesis per service (keyed by serviceId)
     * @param graph         the weighted service dependency graph
     * @return              final propagated confidence C(s) per service
     */
    Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                  ServiceDependencyGraph graph);
}
