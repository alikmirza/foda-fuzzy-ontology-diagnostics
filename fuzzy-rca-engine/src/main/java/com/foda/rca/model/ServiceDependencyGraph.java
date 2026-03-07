package com.foda.rca.model;

import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Weighted directed graph G = (S, E, W) representing inter-service call dependencies.
 *
 * <p>An edge (u → v) with weight w ∈ (0, 1] encodes the following semantics:
 * <em>service {@code u} calls service {@code v}</em>, and {@code w} represents the
 * coupling strength — the probability that a fault originating at {@code v} will cause
 * observable symptoms at {@code u} (the caller).</p>
 *
 * <h2>RCA Semantics</h2>
 *
 * <p>Fault confidence propagates <strong>backward</strong> along the call graph (from callees
 * to callers), because failures at a dependency are experienced by its callers, not its
 * callers' dependents. Concretely:
 * <ul>
 *   <li>Edge {@code gateway → order-svc} (w=0.9) means: gateway calls order-svc,
 *       and a fault at order-svc causes gateway to exhibit symptoms with strength 0.9.</li>
 *   <li>Edge {@code order-svc → db-svc} (w=0.8) means: order-svc calls db-svc,
 *       and a fault at db-svc causes order-svc to exhibit symptoms with strength 0.8.</li>
 *   <li>Therefore a fault at {@code db-svc} propagates backward: db-svc → order-svc → gateway,
 *       with each hop attenuated by the edge weight and an optional damping factor δ.</li>
 * </ul>
 * </p>
 *
 * <p>Example: standard 5-service microservice topology (Section 5.1):
 * <pre>
 *   gateway ──0.90──▶ order-svc ──0.80──▶ inventory-svc
 *                 └──0.75──▶ payment-svc ──0.85──▶ db-svc
 *                                               ↑
 *                            inventory-svc ──0.60──┘
 *
 *   RCA propagation direction (fault at db-svc):
 *   db-svc ←── payment-svc ←── order-svc ←── gateway
 *     └──────── inventory-svc ──┘
 * </pre>
 * </p>
 *
 * <p>Used by {@code ConfidencePropagator} (Section 3.3) to traverse the dependency structure
 * in <em>reverse</em> topological order (callees before callers) and accumulate fault
 * confidence backward along call paths.</p>
 *
 * <p><strong>Thread safety:</strong> instances are effectively immutable once built via
 * {@link Builder}; the builder itself is not thread-safe.</p>
 */
@Slf4j
public class ServiceDependencyGraph {

    /** Adjacency list: caller service → list of (callee, weight) edges. */
    private final Map<String, List<Edge>> adjacency;

    /** Reverse adjacency list: callee → list of (caller, weight) — used for propagation. */
    private final Map<String, List<Edge>> reverseAdjacency;

    /** All service IDs in this graph. */
    private final Set<String> services;

    private ServiceDependencyGraph(Builder builder) {
        this.adjacency        = Collections.unmodifiableMap(deepCopy(builder.adjacency));
        this.reverseAdjacency = Collections.unmodifiableMap(deepCopy(builder.reverseAdjacency));
        this.services         = Collections.unmodifiableSet(new LinkedHashSet<>(builder.services));
    }

    // -------------------------------------------------------------------------
    // Query methods
    // -------------------------------------------------------------------------

    /** Returns all service IDs registered in the graph. */
    public Set<String> getServices() { return services; }

    /**
     * Returns the outgoing edges (calls made) from {@code serviceId}.
     * An empty list is returned for services with no outgoing calls.
     */
    public List<Edge> getOutgoingEdges(String serviceId) {
        return adjacency.getOrDefault(serviceId, List.of());
    }

    /**
     * Returns the incoming edges (callers) of {@code serviceId}.
     * An empty list is returned for entry-point services.
     */
    public List<Edge> getIncomingEdges(String serviceId) {
        return reverseAdjacency.getOrDefault(serviceId, List.of());
    }

    /**
     * Returns a topological ordering of services using Kahn's algorithm (sources first,
     * leaf callees last).
     *
     * <p><strong>RCA note:</strong> For backward confidence propagation (callees → callers),
     * callers pass this list through {@link java.util.Collections#reverse(java.util.List)} to
     * obtain the reverse order (leaf callees first, entry-point callers last). This ensures
     * that C(t) for each callee {@code t} is finalised before it contributes to C(s) of
     * any caller {@code s} that depends on {@code t}.</p>
     *
     * @return forward topological order (use {@link java.util.Collections#reverse} for RCA propagation)
     * @throws IllegalStateException if the graph contains a cycle; use
     *         {@link com.foda.rca.propagation.IterativeConfidencePropagator} for cyclic graphs
     */
    public List<String> topologicalOrder() {
        Map<String, Integer> inDegree = new HashMap<>();
        for (String s : services) inDegree.put(s, 0);
        for (String s : services) {
            for (Edge e : getOutgoingEdges(s)) {
                inDegree.merge(e.getTarget(), 1, Integer::sum);
            }
        }

        Queue<String> queue = new ArrayDeque<>();
        for (Map.Entry<String, Integer> entry : inDegree.entrySet()) {
            if (entry.getValue() == 0) queue.add(entry.getKey());
        }

        List<String> order = new ArrayList<>();
        while (!queue.isEmpty()) {
            String s = queue.poll();
            order.add(s);
            for (Edge e : getOutgoingEdges(s)) {
                int newDeg = inDegree.merge(e.getTarget(), -1, Integer::sum);
                if (newDeg == 0) queue.add(e.getTarget());
            }
        }

        if (order.size() != services.size()) {
            throw new IllegalStateException(
                "Service dependency graph contains a cycle; topological sort is undefined.");
        }
        return order;
    }

    // -------------------------------------------------------------------------
    // Inner types
    // -------------------------------------------------------------------------

    /**
     * A directed, weighted edge representing a service call: {@code source → target}.
     *
     * <p><strong>Semantics:</strong> {@code source} calls {@code target}. The {@code weight}
     * ∈ (0, 1] is the coupling strength — the probability that a fault at {@code target}
     * (the callee/dependency) will propagate observable symptoms to {@code source} (the caller).
     * A weight of 1.0 means every fault at {@code target} is visible at {@code source};
     * lower weights model partial coupling (e.g. non-critical downstream paths, retried calls).</p>
     *
     * <p>Example: {@code Edge("order-svc", "db-svc", 0.85)} means order-svc calls db-svc,
     * and 85% of db-svc faults manifest as symptoms in order-svc.</p>
     */
    public record Edge(String source, String target, double weight) {
        public Edge {
            Objects.requireNonNull(source, "source");
            Objects.requireNonNull(target, "target");
            if (weight <= 0.0 || weight > 1.0)
                throw new IllegalArgumentException("Edge weight must be in (0, 1], got: " + weight);
        }
        /** Convenience alias matching the adjacency direction. */
        public String getTarget() { return target; }
        public String getSource() { return source; }
        public double getWeight() { return weight; }
    }

    // -------------------------------------------------------------------------
    // Builder
    // -------------------------------------------------------------------------

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private final Map<String, List<Edge>> adjacency        = new LinkedHashMap<>();
        private final Map<String, List<Edge>> reverseAdjacency = new LinkedHashMap<>();
        private final Set<String> services = new LinkedHashSet<>();

        /** Register a service node (required before adding edges). */
        public Builder addService(String serviceId) {
            services.add(serviceId);
            adjacency.computeIfAbsent(serviceId, k -> new ArrayList<>());
            reverseAdjacency.computeIfAbsent(serviceId, k -> new ArrayList<>());
            return this;
        }

        /**
         * Add a directed, weighted dependency edge: {@code caller} → {@code callee}.
         *
         * <p><strong>RCA semantics:</strong> {@code caller} calls {@code callee}. A fault at
         * {@code callee} propagates backward to {@code caller} with the given {@code weight}.
         * Higher weights mean stronger coupling — the caller is more likely to exhibit symptoms
         * when the callee is faulty.</p>
         *
         * @param caller the upstream (calling) service; {@code source} of the edge
         * @param callee the downstream (called) service; {@code target} of the edge
         * @param weight coupling strength ∈ (0, 1]: probability that callee's fault manifests at caller
         */
        public Builder addEdge(String caller, String callee, double weight) {
            services.add(caller);
            services.add(callee);
            adjacency.computeIfAbsent(caller, k -> new ArrayList<>())
                     .add(new Edge(caller, callee, weight));
            reverseAdjacency.computeIfAbsent(callee, k -> new ArrayList<>())
                            .add(new Edge(caller, callee, weight));
            return this;
        }

        public ServiceDependencyGraph build() { return new ServiceDependencyGraph(this); }
    }

    /**
     * Returns {@code true} if this graph contains at least one directed cycle.
     *
     * <p>Implemented as a lightweight wrapper around {@link #topologicalOrder()}: if Kahn's
     * algorithm completes successfully the graph is acyclic (returns {@code false}); if it
     * throws an {@link IllegalStateException} (cycle detected) this method returns
     * {@code true}.</p>
     *
     * <p>Used by {@link com.foda.rca.propagation.AdaptiveConfidencePropagator} and
     * {@link com.foda.rca.core.FuzzyRcaEngineImpl} to auto-select the appropriate propagator.</p>
     *
     * @return {@code true} iff the graph is cyclic
     */
    public boolean hasCycle() {
        try {
            topologicalOrder();
            return false;
        } catch (IllegalStateException e) {
            return true;
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Map<String, List<Edge>> deepCopy(Map<String, List<Edge>> src) {
        Map<String, List<Edge>> copy = new LinkedHashMap<>();
        src.forEach((k, v) -> copy.put(k, new ArrayList<>(v)));
        return copy;
    }
}
