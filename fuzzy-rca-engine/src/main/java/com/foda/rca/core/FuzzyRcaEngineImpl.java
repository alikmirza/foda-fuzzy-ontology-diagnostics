package com.foda.rca.core;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.explanation.ExplanationBuilder;
import com.foda.rca.explanation.NaturalLanguageExplanationBuilder;
import com.foda.rca.explanation.OntologyGroundedExplanationBuilder;
import com.foda.rca.fuzzification.FaultFuzzifier;
import com.foda.rca.fuzzification.FaultFuzzifierImpl;
import com.foda.rca.inference.FuzzyRuleEngine;
import com.foda.rca.inference.MamdaniFuzzyRuleEngine;
import com.foda.rca.model.*;
import com.foda.rca.propagation.AdaptiveConfidencePropagator;
import com.foda.rca.propagation.ConfidencePropagator;
import com.foda.rca.ranking.CauseRanker;
import com.foda.rca.ranking.TopKCauseRanker;
import lombok.extern.slf4j.Slf4j;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Orchestrating implementation of the FCP-RCA five-phase pipeline.
 *
 * <h2>Pipeline (Section 3 overview)</h2>
 * <pre>
 *  ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐
 *  │ ServiceMetrics│→│ FaultFuzzifier│→│ FuzzyVector per svc  │
 *  └─────────────┘   └──────────────┘   └────────────────────┘
 *                                                ↓
 *                                       ┌────────────────────┐
 *                                       │ FuzzyRuleEngine    │  (Mamdani)
 *                                       │ → FaultHypothesis  │
 *                                       └────────────────────┘
 *                                                ↓
 *                                       ┌────────────────────┐
 *                                       │ ConfidencePropagator│ (Noisy-OR)
 *                                       │ → C(s) per service  │
 *                                       └────────────────────┘
 *                                                ↓
 *                                       ┌────────────────────┐
 *                                       │ CauseRanker (top-k) │
 *                                       └────────────────────┘
 *                                                ↓
 *                                       ┌────────────────────┐
 *                                       │ ExplanationBuilder  │
 *                                       └────────────────────┘
 *                                                ↓
 *                                         DiagnosisResult
 * </pre>
 *
 * <p><strong>Thread safety:</strong> all collaborators are stateless; this class is
 * therefore thread-safe and safe to use as a Spring singleton.</p>
 *
 * <h2>Construction</h2>
 * <p>Use {@link #withDefaults()} for a production-ready instance, or
 * {@link Builder} to inject custom implementations for testing or extension.</p>
 */
@Slf4j
public class FuzzyRcaEngineImpl implements FuzzyRcaEngine {

    private final FaultFuzzifier      fuzzifier;
    private final FuzzyRuleEngine     ruleEngine;
    private final ConfidencePropagator propagator;
    private final CauseRanker          ranker;
    private final ExplanationBuilder   explanationBuilder;

    /** Package-private constructor; use {@link Builder} or {@link #withDefaults()}. */
    FuzzyRcaEngineImpl(FaultFuzzifier fuzzifier,
                       FuzzyRuleEngine ruleEngine,
                       ConfidencePropagator propagator,
                       CauseRanker ranker,
                       ExplanationBuilder explanationBuilder) {
        this.fuzzifier          = Objects.requireNonNull(fuzzifier);
        this.ruleEngine         = Objects.requireNonNull(ruleEngine);
        this.propagator         = Objects.requireNonNull(propagator);
        this.ranker             = Objects.requireNonNull(ranker);
        this.explanationBuilder = Objects.requireNonNull(explanationBuilder);
    }

    // -----------------------------------------------------------------------
    // Factory methods
    // -----------------------------------------------------------------------

    /**
     * Creates an engine with all default implementations — suitable for production use
     * and as the baseline for experimental evaluation (Section 5).
     */
    public static FuzzyRcaEngineImpl withDefaults() {
        return new Builder().build();
    }

    public static Builder builder() { return new Builder(); }

    // -----------------------------------------------------------------------
    // Core pipeline
    // -----------------------------------------------------------------------

    /**
     * {@inheritDoc}
     *
     * <h3>Phase-by-phase log messages</h3>
     * <p>Each phase logs at DEBUG level with per-service details and at INFO level
     * for phase-level summaries, facilitating experimental trace logging.</p>
     */
    @Override
    public DiagnosisResult diagnose(List<ServiceMetrics> metricObservations,
                                    ServiceDependencyGraph dependencyGraph,
                                    int topK) {
        validateInputs(metricObservations, dependencyGraph, topK);
        String diagId = UUID.randomUUID().toString();
        Instant ts    = Instant.now();
        log.info("[{}] FCP-RCA pipeline started: {} services, topK={}",
                 diagId, metricObservations.size(), topK);

        // ── Phase 1: Fuzzification ──────────────────────────────────────────
        log.info("[{}] Phase 1: Fuzzification", diagId);
        Map<String, FuzzyVector> fuzzyVectors = new LinkedHashMap<>();
        for (ServiceMetrics m : metricObservations) {
            FuzzyVector fv = fuzzifier.fuzzify(m);
            fuzzyVectors.put(m.getServiceId(), fv);
        }

        // ── Phase 2: Fault Inference (Mamdani) ─────────────────────────────
        log.info("[{}] Phase 2: Fault inference (Mamdani)", diagId);
        Map<String, FaultHypothesis> hypotheses = new LinkedHashMap<>();
        for (Map.Entry<String, FuzzyVector> entry : fuzzyVectors.entrySet()) {
            FaultHypothesis hyp = ruleEngine.infer(entry.getValue());
            hypotheses.put(entry.getKey(), hyp);
            log.debug("[{}]   {} → H={}, category={}",
                      diagId, entry.getKey(), hyp.getLocalConfidence(),
                      hyp.getDominantFaultCategory());
        }

        // ── Phase 3: Confidence Propagation (Noisy-OR) ─────────────────────
        log.info("[{}] Phase 3: Confidence propagation (Noisy-OR)", diagId);
        Map<String, Double> propagatedConf = propagator.propagate(hypotheses, dependencyGraph);
        propagatedConf.forEach((svc, c) ->
            log.debug("[{}]   {} → C={}", diagId, svc, c));

        // ── Phase 4: Top-k Ranking ──────────────────────────────────────────
        log.info("[{}] Phase 4: Top-{} ranking", diagId, topK);
        List<RankedCause> rankedCauses = ranker.rank(propagatedConf, hypotheses,
                                                      dependencyGraph, topK);

        // ── Phase 5: Explanation Generation ────────────────────────────────
        log.info("[{}] Phase 5: Explanation generation", diagId);
        List<RankedCause> explained = rankedCauses.stream()
                .map(cause -> {
                    FuzzyVector vec = fuzzyVectors.getOrDefault(
                            cause.getServiceId(), emptyVector(cause.getServiceId()));
                    FaultHypothesis hyp = hypotheses.getOrDefault(
                            cause.getServiceId(), emptyHypothesis(cause.getServiceId()));
                    String text = explanationBuilder.explain(cause, vec, hyp);
                    return RankedCause.builder()
                            .rank(cause.getRank())
                            .serviceId(cause.getServiceId())
                            .finalConfidence(cause.getFinalConfidence())
                            .localConfidence(cause.getLocalConfidence())
                            .propagatedConfidence(cause.getPropagatedConfidence())
                            .faultCategory(cause.getFaultCategory())
                            .causalPath(cause.getCausalPath())
                            .explanation(text)
                            .build();
                })
                .collect(Collectors.toList());

        log.info("[{}] FCP-RCA complete: {} root cause(s) identified. Top: {} (C={})",
                 diagId,
                 explained.size(),
                 explained.isEmpty() ? "none" : explained.get(0).getServiceId(),
                 explained.isEmpty() ? 0.0   : explained.get(0).getFinalConfidence());

        // Assemble full result
        long edgeCount = dependencyGraph.getServices().stream()
                .mapToLong(s -> dependencyGraph.getOutgoingEdges(s).size())
                .sum();

        return DiagnosisResult.builder()
                .diagnosisId(diagId)
                .timestamp(ts)
                .rankedCauses(explained)
                .fuzzyVectors(Collections.unmodifiableMap(fuzzyVectors))
                .faultHypotheses(Collections.unmodifiableMap(hypotheses))
                .propagatedConfidences(propagatedConf)
                .serviceCount(dependencyGraph.getServices().size())
                .edgeCount((int) edgeCount)
                .build();
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private static void validateInputs(List<ServiceMetrics> obs,
                                        ServiceDependencyGraph graph, int k) {
        if (obs == null || obs.isEmpty())
            throw new IllegalArgumentException("metricObservations must not be empty");
        if (graph == null)
            throw new IllegalArgumentException("dependencyGraph must not be null");
        if (k <= 0)
            throw new IllegalArgumentException("topK must be > 0");
    }

    private static FuzzyVector emptyVector(String serviceId) {
        return FuzzyVector.builder().serviceId(serviceId).memberships(Map.of()).build();
    }

    private static FaultHypothesis emptyHypothesis(String serviceId) {
        return FaultHypothesis.builder()
                .serviceId(serviceId).localConfidence(0.0)
                .dominantFaultCategory("UNKNOWN")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    // -----------------------------------------------------------------------
    // Builder
    // -----------------------------------------------------------------------

    /**
     * Fluent builder for {@link FuzzyRcaEngineImpl}.
     *
     * <p>Any component not set explicitly falls back to its default implementation,
     * making it easy to swap in a custom rule engine or propagator without touching
     * other layers.</p>
     *
     * <h3>Propagator auto-selection</h3>
     *
     * <p>The default propagator is {@link com.foda.rca.propagation.AdaptiveConfidencePropagator}
     * (δ = 0.85), which automatically selects:
     * <ul>
     *   <li>{@link com.foda.rca.propagation.DampedConfidencePropagator} for acyclic graphs
     *       (O(|S|+|E|) exact pass).</li>
     *   <li>{@link com.foda.rca.propagation.IterativeConfidencePropagator} for cyclic graphs
     *       (Jacobi fixed-point, Banach-guaranteed convergence).</li>
     * </ul>
     * This eliminates the need to manually call {@link #cycleSafe(double)} for graphs that
     * might contain health-check cycles or bidirectional edges.</p>
     *
     * <h3>Quick configuration presets</h3>
     * <pre>
     *   // Full FCP-RCA (recommended for paper) — auto-selects propagator
     *   FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build()
     *
     *   // Default build: adaptive propagator with δ=0.85 (works for acyclic AND cyclic)
     *   FuzzyRcaEngineImpl.builder().build()
     *
     *   // Ablation: no propagation (LocalOnly baseline)
     *   FuzzyRcaEngineImpl.builder().propagator(new LocalOnlyPropagator()).build()
     *
     *   // Ablation: uniform weights
     *   FuzzyRcaEngineImpl.builder().propagator(new UniformWeightPropagator(0.85)).build()
     *
     *   // Ablation: no damping (δ = 1, still adaptive)
     *   FuzzyRcaEngineImpl.builder().withDampingFactor(1.0).build()
     *
     *   // Explicit cycle-safe iterative propagator (for cyclic-only deployments)
     *   FuzzyRcaEngineImpl.builder().cycleSafe(0.85).build()
     * </pre>
     */
    public static final class Builder {
        private FaultFuzzifier       fuzzifier          = new FaultFuzzifierImpl();
        private FuzzyRuleEngine      ruleEngine         = new MamdaniFuzzyRuleEngine();
        private ConfidencePropagator propagator         = new AdaptiveConfidencePropagator();
        private CauseRanker          ranker             = new TopKCauseRanker();
        private ExplanationBuilder   explanationBuilder = new NaturalLanguageExplanationBuilder();

        public Builder fuzzifier(FaultFuzzifier f)             { this.fuzzifier = f;          return this; }
        public Builder ruleEngine(FuzzyRuleEngine e)           { this.ruleEngine = e;         return this; }
        public Builder propagator(ConfidencePropagator p)      { this.propagator = p;         return this; }
        public Builder ranker(CauseRanker r)                   { this.ranker = r;             return this; }
        public Builder explanationBuilder(ExplanationBuilder b){ this.explanationBuilder = b; return this; }

        /**
         * Convenience: swap the default {@link NaturalLanguageExplanationBuilder} for the
         * ontology-grounded variant that pulls fault labels, contributing factors and
         * remediation text from {@code DiagnosticKB.owl}.
         *
         * <p>Opt-in only — the default benchmark configuration is unchanged so existing
         * results in Section 5 of the paper remain reproducible bit-for-bit.</p>
         */
        public Builder withOntologyGroundedExplanations() {
            this.explanationBuilder = new OntologyGroundedExplanationBuilder();
            return this;
        }

        /**
         * Sets the damping factor δ and activates the adaptive propagator (Eq. 4 / Eq. 5).
         *
         * <p>The adaptive propagator auto-selects:
         * <ul>
         *   <li>{@link AdaptiveConfidencePropagator} → {@link DampedConfidencePropagator}
         *       for acyclic graphs (Eq. 4).</li>
         *   <li>{@link AdaptiveConfidencePropagator} → {@link IterativeConfidencePropagator}
         *       for cyclic graphs (Eq. 5).</li>
         * </ul>
         * This is the recommended setting for the full FCP-RCA algorithm.</p>
         *
         * @param delta damping factor δ ∈ (0, 1]; use 0.85 for the paper's default
         */
        public Builder withDampingFactor(double delta) {
            this.propagator = new AdaptiveConfidencePropagator(delta);
            return this;
        }

        /**
         * Activates the cycle-safe iterative propagator (Eq. 5) with the given damping
         * factor. Safe for graphs that may contain bidirectional edges or health-check cycles.
         *
         * @param delta damping factor δ ∈ (0, 1]; use 0.85 for the paper's default
         */
        public Builder cycleSafe(double delta) {
            this.propagator = new com.foda.rca.propagation.IterativeConfidencePropagator(
                    delta,
                    com.foda.rca.propagation.IterativeConfidencePropagator.DEFAULT_EPSILON,
                    com.foda.rca.propagation.IterativeConfidencePropagator.DEFAULT_MAX_ITERATIONS);
            return this;
        }

        public FuzzyRcaEngineImpl build() {
            return new FuzzyRcaEngineImpl(fuzzifier, ruleEngine, propagator,
                                          ranker, explanationBuilder);
        }
    }
}
