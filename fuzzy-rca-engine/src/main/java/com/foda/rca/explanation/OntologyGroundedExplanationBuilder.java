package com.foda.rca.explanation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.RankedCause;
import org.apache.jena.ontology.OntModel;
import org.apache.jena.ontology.OntModelSpec;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QueryExecutionFactory;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.QuerySolution;
import org.apache.jena.query.ResultSet;
import org.apache.jena.rdf.model.ModelFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Ontology-grounded explanation builder for FCP-RCA diagnoses.
 *
 * <p>Companion to {@link NaturalLanguageExplanationBuilder} (the legacy template-only
 * baseline retained for paper comparison). This implementation enriches each explanation
 * with three pieces of knowledge pulled from {@code DiagnosticKB.owl}:</p>
 * <ol>
 *   <li>The OWL fault prototype IRI (e.g. {@code diagnostic:LatencySpike}) and its label,
 *       making the explanation unambiguously linkable to the knowledge base.</li>
 *   <li>The ordered list of {@code ContributingFactor} individuals attached to that
 *       fault prototype, surfaced as a new "Contributing factors" paragraph.</li>
 *   <li>The {@code Recommendation} individual's description, used in place of the legacy
 *       hard-coded remediation switch.</li>
 * </ol>
 *
 * <p>The output preserves the legacy paragraph order — Summary, Observed symptoms,
 * Fired inference rules, <strong>Contributing factors (new)</strong>, Causal propagation
 * path, Recommended action — giving a six-paragraph structure (legacy is five).</p>
 *
 * <h3>Performance</h3>
 * <p>The ontology is loaded once at construction and all per-fault enrichments are
 * pre-computed via SPARQL into an immutable in-memory map. {@link #explain(RankedCause,
 * FuzzyVector, FaultHypothesis)} performs only map lookups and string assembly — no
 * Jena query is executed on the hot path.</p>
 *
 * <h3>Failure modes</h3>
 * <p>Construction will throw if the ontology cannot be located or parsed. After
 * successful construction, {@code explain()} never throws: unmapped fault categories
 * fall back to a {@link #FALLBACK_ENRICHMENT generic enrichment} and emit a WARN log.</p>
 */
public class OntologyGroundedExplanationBuilder implements ExplanationBuilder {

    private static final Logger log = LoggerFactory.getLogger(OntologyGroundedExplanationBuilder.class);

    /** Default classpath location of the populated {@code DiagnosticKB.owl}. */
    public static final String DEFAULT_ONTOLOGY_RESOURCE = "ontology/DiagnosticKB.owl";

    /** Ontology base namespace; matches {@code <owl:Ontology rdf:about="..."/>} in the OWL file. */
    public static final String ONTOLOGY_NS = "http://foda.com/ontology/diagnostic#";

    /** Short prefix for the ontology namespace, used in the rendered IRI ({@code diagnostic:CpuSaturation}). */
    public static final String ONTOLOGY_PREFIX = "diagnostic";

    // ---------------------------------------------------------------------
    // Vocabulary mapping (Task 4)
    // ---------------------------------------------------------------------
    //
    // The fuzzy-rca-engine's FaultHypothesis emits these category strings:
    //   CPU_SATURATION, LATENCY_ANOMALY, MEMORY_PRESSURE, SERVICE_ERROR,
    //   RESOURCE_CONTENTION, CASCADING_FAILURE, NORMAL, UNKNOWN.
    //
    // The DiagnosticKB.owl ontology defines these fault prototype individuals:
    //   CpuSaturation, MemoryLeak, LatencySpike, HighErrorRate, ResourceContention,
    //   NetworkCongestion, ThroughputDegradation, DiskIoBottleneck.
    //
    // CASCADING_FAILURE has no dedicated ontology counterpart — we map it to
    // ResourceContention as the closest semantic match (cascading failure typically
    // manifests as multi-resource saturation across a dependency chain).
    //
    // NORMAL / UNKNOWN have no fault prototype; explain() falls back gracefully.
    private static final Map<String, String> CATEGORY_TO_FAULT_LOCAL_NAME =
            Map.of(
                    "CPU_SATURATION",     "CpuSaturation",
                    "LATENCY_ANOMALY",    "LatencySpike",
                    "MEMORY_PRESSURE",    "MemoryLeak",
                    "SERVICE_ERROR",      "HighErrorRate",
                    "RESOURCE_CONTENTION","ResourceContention",
                    "CASCADING_FAILURE",  "ResourceContention");

    // ---------------------------------------------------------------------
    // Symptom-label prose (mirrors legacy builder so output reads similarly)
    // ---------------------------------------------------------------------
    private static final Map<String, String> LABEL_DESCRIPTIONS = Map.ofEntries(
            Map.entry("cpu_HIGH",          "CPU utilisation is HIGH"),
            Map.entry("cpu_MEDIUM",        "CPU utilisation is MEDIUM"),
            Map.entry("cpu_LOW",           "CPU utilisation is LOW"),
            Map.entry("latency_CRITICAL",  "request latency is CRITICAL"),
            Map.entry("latency_ELEVATED",  "request latency is ELEVATED"),
            Map.entry("latency_NORMAL",    "request latency is NORMAL"),
            Map.entry("memory_HIGH",       "memory utilisation is HIGH"),
            Map.entry("memory_MEDIUM",     "memory utilisation is MEDIUM"),
            Map.entry("memory_LOW",        "memory utilisation is LOW"),
            Map.entry("errorRate_HIGH",    "error rate is HIGH"),
            Map.entry("errorRate_ELEVATED","error rate is ELEVATED"),
            Map.entry("errorRate_LOW",     "error rate is LOW"),
            Map.entry("errorRate_NONE",    "error rate is NORMAL"),
            Map.entry("throughput_LOW",    "throughput is LOW"),
            Map.entry("throughput_NORMAL", "throughput is NORMAL"));

    /**
     * Fallback used when no ontology mapping or query result is available
     * (e.g. fault category {@code NORMAL} or {@code UNKNOWN}).
     */
    private static final OntologyEnrichment FALLBACK_ENRICHMENT = new OntologyEnrichment(
            null,
            "undetermined fault",
            List.of(),
            "Perform detailed triage and review recent deployment changes.");

    // ---------------------------------------------------------------------
    // Pre-cached enrichments
    // ---------------------------------------------------------------------
    private final Map<String, OntologyEnrichment> enrichmentByCategory;

    // ---------------------------------------------------------------------
    // Construction
    // ---------------------------------------------------------------------

    /**
     * Loads {@link #DEFAULT_ONTOLOGY_RESOURCE} from the classpath and pre-caches
     * one {@link OntologyEnrichment} per known fault category.
     */
    public OntologyGroundedExplanationBuilder() {
        this(DEFAULT_ONTOLOGY_RESOURCE);
    }

    /**
     * Loads an ontology from the given classpath resource and pre-caches enrichments.
     *
     * @param classpathResource path to an OWL/RDF-XML file on the classpath
     */
    public OntologyGroundedExplanationBuilder(String classpathResource) {
        OntModel model = loadOntology(classpathResource);
        this.enrichmentByCategory = Collections.unmodifiableMap(precomputeEnrichments(model));
        log.info("OntologyGroundedExplanationBuilder ready: {} categories pre-cached from {}",
                enrichmentByCategory.size(), classpathResource);
    }

    private static OntModel loadOntology(String classpathResource) {
        OntModel m = ModelFactory.createOntologyModel(OntModelSpec.OWL_MEM);
        ClassLoader cl = OntologyGroundedExplanationBuilder.class.getClassLoader();
        try (InputStream in = cl.getResourceAsStream(classpathResource)) {
            if (in == null) {
                throw new IllegalStateException(
                        "Ontology resource not found on classpath: " + classpathResource);
            }
            m.read(in, null, "RDF/XML");
        } catch (Exception e) {
            throw new IllegalStateException(
                    "Failed to load ontology from " + classpathResource, e);
        }
        return m;
    }

    private static Map<String, OntologyEnrichment> precomputeEnrichments(OntModel model) {
        Map<String, OntologyEnrichment> out = new LinkedHashMap<>();
        for (Map.Entry<String, String> e : CATEGORY_TO_FAULT_LOCAL_NAME.entrySet()) {
            String category  = e.getKey();
            String localName = e.getValue();
            OntologyEnrichment enr = queryEnrichment(model, localName);
            if (enr == null) {
                log.warn("No ontology enrichment found for category '{}' (mapped to {}{}); using fallback",
                        category, ONTOLOGY_PREFIX + ":", localName);
                enr = FALLBACK_ENRICHMENT;
            }
            out.put(category, enr);
        }
        return out;
    }

    /**
     * Runs the SPARQL bundle for one fault prototype and returns the assembled
     * {@link OntologyEnrichment}, or {@code null} if the prototype carries no label
     * (treated as "not in ontology"). Recommendation and contributing factors may
     * legitimately be empty and are returned as such.
     */
    private static OntologyEnrichment queryEnrichment(OntModel model, String faultLocalName) {
        // Label
        String labelQuery = String.format("""
                PREFIX diagnostic: <%s>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?label WHERE { diagnostic:%s rdfs:label ?label . } LIMIT 1
                """, ONTOLOGY_NS, faultLocalName);
        String label = firstString(model, labelQuery, "label");
        if (label == null) {
            return null;
        }

        // Recommendation description
        String recQuery = String.format("""
                PREFIX diagnostic: <%s>
                SELECT ?desc WHERE {
                    diagnostic:%s diagnostic:hasRecommendation ?rec .
                    ?rec diagnostic:description ?desc .
                } LIMIT 1
                """, ONTOLOGY_NS, faultLocalName);
        String recommendation = firstString(model, recQuery, "desc");

        // Contributing factors ordered by importance desc
        String factorsQuery = String.format("""
                PREFIX diagnostic: <%s>
                SELECT ?metricName ?importance ?desc WHERE {
                    diagnostic:%s diagnostic:hasContributingFactor ?cf .
                    ?cf diagnostic:metricName ?metricName .
                    ?cf diagnostic:importance ?importance .
                    ?cf diagnostic:description ?desc .
                }
                ORDER BY DESC(?importance)
                """, ONTOLOGY_NS, faultLocalName);

        List<ContributingFactor> factors = new ArrayList<>();
        try (QueryExecution qe = QueryExecutionFactory.create(QueryFactory.create(factorsQuery), model)) {
            ResultSet rs = qe.execSelect();
            while (rs.hasNext()) {
                QuerySolution s = rs.nextSolution();
                String name = s.contains("metricName") ? s.getLiteral("metricName").getString() : "";
                double imp  = s.contains("importance") ? s.getLiteral("importance").getDouble() : 0.0;
                String desc = s.contains("desc")       ? s.getLiteral("desc").getString()       : "";
                factors.add(new ContributingFactor(name, imp, desc));
            }
        }

        return new OntologyEnrichment(faultLocalName, label, factors, recommendation);
    }

    private static String firstString(OntModel model, String sparql, String var) {
        try (QueryExecution qe = QueryExecutionFactory.create(QueryFactory.create(sparql), model)) {
            ResultSet rs = qe.execSelect();
            if (rs.hasNext()) {
                QuerySolution s = rs.nextSolution();
                if (s.contains(var) && s.getLiteral(var) != null) {
                    return s.getLiteral(var).getString();
                }
            }
        }
        return null;
    }

    // ---------------------------------------------------------------------
    // ExplanationBuilder API
    // ---------------------------------------------------------------------

    @Override
    public String explain(RankedCause cause, FuzzyVector vector, FaultHypothesis hypothesis) {
        String category = cause.getFaultCategory();
        OntologyEnrichment enr = enrichmentByCategory.getOrDefault(category, FALLBACK_ENRICHMENT);

        StringBuilder sb = new StringBuilder();

        // Paragraph 1 — Summary (with ontology IRI)
        String iriPhrase = enr.faultLocalName() == null
                ? enr.label()
                : String.format("%s (%s:%s)", enr.label(), ONTOLOGY_PREFIX, enr.faultLocalName());
        sb.append(String.format(
                "Service '%s' is ranked #%d as a root-cause candidate with a final fault confidence "
                        + "of %.1f%% (C=%.4f).  The dominant fault pattern is: %s.",
                cause.getServiceId(),
                cause.getRank(),
                cause.getFinalConfidence() * 100.0,
                cause.getFinalConfidence(),
                iriPhrase));

        // Paragraph 2 — Observed symptoms
        sb.append("\n\nObserved symptoms: ");
        List<String> topSymptoms = vector.getMemberships().entrySet().stream()
                .filter(e -> e.getValue() > 0.15)
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(4)
                .map(e -> String.format("%s (μ=%.2f)",
                        LABEL_DESCRIPTIONS.getOrDefault(e.getKey(), e.getKey()),
                        e.getValue()))
                .collect(Collectors.toList());
        sb.append(topSymptoms.isEmpty()
                ? "no significant deviations detected."
                : String.join("; ", topSymptoms) + ".");

        // Paragraph 3 — Fired inference rules
        sb.append("\n\nFired inference rules: ");
        if (hypothesis.getFiredRules().isEmpty()) {
            sb.append("none — local evidence is below inference threshold.");
        } else {
            Map<String, Double> strengths = hypothesis.getRuleFireStrengths();
            String rulesText = hypothesis.getFiredRules().stream()
                    .limit(4)
                    .map(r -> String.format("'%s' (α=%.2f)", r,
                            strengths.getOrDefault(r, 0.0)))
                    .collect(Collectors.joining(", "));
            sb.append(rulesText).append(String.format(
                    ".  Local hypothesis confidence: H=%.4f.", hypothesis.getLocalConfidence()));
        }

        // Paragraph 4 — Contributing factors (NEW, ontology-sourced)
        sb.append("\n\nContributing factors (from knowledge base): ");
        if (enr.factors().isEmpty()) {
            sb.append("none catalogued for this fault pattern.");
        } else {
            // Descriptions in DiagnosticKB.owl already terminate with a period; strip
            // any trailing punctuation before joining so "; " never sits next to "."
            // and the closing sentence end is exactly one period.
            String factorsText = enr.factors().stream()
                    .limit(2)
                    .map(f -> String.format("%s (importance=%.2f) — %s",
                            f.metricName(), f.importance(), stripTrailingPeriod(f.description())))
                    .collect(Collectors.joining("; "));
            sb.append(factorsText).append('.');
        }

        // Paragraph 5 — Causal propagation path
        sb.append("\n\nCausal propagation path: ");
        if (cause.getCausalPath() == null || cause.getCausalPath().size() <= 1) {
            sb.append("no upstream services contributed — fault is locally originating.");
        } else {
            sb.append(String.join(" → ", cause.getCausalPath()));
            sb.append(String.format(
                    ".  Upstream propagation contributed %.1f%% additional confidence (P=%.4f).",
                    cause.getPropagatedConfidence() * 100.0,
                    cause.getPropagatedConfidence()));
        }

        // Paragraph 6 — Recommended action (ontology Recommendation, not the hard-coded switch)
        sb.append("\n\nRecommended action: ");
        sb.append(enr.recommendation() == null || enr.recommendation().isBlank()
                ? FALLBACK_ENRICHMENT.recommendation()
                : enr.recommendation());

        return sb.toString();
    }

    // ---------------------------------------------------------------------
    // Test/observability accessors
    // ---------------------------------------------------------------------

    /** Returns an unmodifiable view of the pre-cached enrichments, keyed by fault category. */
    public Map<String, OntologyEnrichment> enrichmentByCategory() {
        return enrichmentByCategory;
    }

    /** Vocabulary-mapping table (category → OWL fault local name); for tests and inspection. */
    public static Map<String, String> categoryToFaultLocalName() {
        return CATEGORY_TO_FAULT_LOCAL_NAME;
    }

    private static String stripTrailingPeriod(String s) {
        if (s == null) return "";
        return s.endsWith(".") ? s.substring(0, s.length() - 1) : s;
    }

    // ---------------------------------------------------------------------
    // Value records (Java 17)
    // ---------------------------------------------------------------------

    /**
     * One row pulled from the ontology for a fault prototype: label, IRI local name,
     * ordered contributing factors, and recommendation description.
     */
    public record OntologyEnrichment(
            String faultLocalName,
            String label,
            List<ContributingFactor> factors,
            String recommendation) {}

    public record ContributingFactor(String metricName, double importance, String description) {}
}
