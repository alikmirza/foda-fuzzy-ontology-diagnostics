package com.foda.rca.inference;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import lombok.extern.slf4j.Slf4j;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Mamdani-style fuzzy rule engine implementing the Fault Inference Layer (Section 3.2).
 *
 * <h2>Algorithm</h2>
 * <ol>
 *   <li><strong>Fire rules:</strong> For each rule r, compute firing strength
 *       α_r = CF_r × min{ μ(a) : a ∈ antecedents(r) }.</li>
 *   <li><strong>Group by consequent:</strong> Collect all α_r per fault category.</li>
 *   <li><strong>Max-aggregate per category:</strong>
 *       strength(cat) = max{ α_r : consequent(r) = cat }
 *       (Mamdani max-aggregation of output fuzzy sets).</li>
 *   <li><strong>Global confidence:</strong> H = max{ strength(cat) } over all categories.</li>
 *   <li><strong>Dominant category:</strong> argmax{ strength(cat) }.</li>
 * </ol>
 *
 * <h2>Built-in Rule Base</h2>
 *
 * <p>The default rule base encodes 18 expert rules covering six fault categories.
 * The certainty factors are calibrated to common microservice failure patterns reported
 * in the literature (Chen et al., 2019; Ma et al., 2020):</p>
 *
 * <table border="1">
 *   <tr><th>Category</th><th>Representative rule</th><th>CF</th></tr>
 *   <tr><td>CPU_SATURATION</td>
 *       <td>IF cpu_HIGH AND latency_ELEVATED THEN CPU_SATURATION</td><td>0.85</td></tr>
 *   <tr><td>MEMORY_PRESSURE</td>
 *       <td>IF memory_HIGH AND throughput_LOW THEN MEMORY_PRESSURE</td><td>0.80</td></tr>
 *   <tr><td>SERVICE_ERROR</td>
 *       <td>IF errorRate_HIGH THEN SERVICE_ERROR</td><td>0.90</td></tr>
 *   <tr><td>LATENCY_ANOMALY</td>
 *       <td>IF latency_CRITICAL THEN LATENCY_ANOMALY</td><td>0.88</td></tr>
 *   <tr><td>CASCADING_FAILURE</td>
 *       <td>IF cpu_HIGH AND errorRate_ELEVATED AND latency_ELEVATED THEN CASCADING_FAILURE</td>
 *       <td>0.92</td></tr>
 *   <tr><td>NORMAL</td>
 *       <td>IF cpu_LOW AND errorRate_NONE AND latency_NORMAL THEN NORMAL</td><td>0.95</td></tr>
 * </table>
 */
@Slf4j
public class MamdaniFuzzyRuleEngine implements FuzzyRuleEngine {

    private final List<FuzzyRule> ruleBase;

    /** Creates an engine with the built-in default rule base (hard-coded in Java). */
    public MamdaniFuzzyRuleEngine() {
        this.ruleBase = buildDefaultRuleBase();
    }

    /** Creates an engine with a custom rule base (for experimentation / extension). */
    public MamdaniFuzzyRuleEngine(List<FuzzyRule> customRules) {
        if (customRules == null || customRules.isEmpty())
            throw new IllegalArgumentException("Rule base must not be empty");
        this.ruleBase = List.copyOf(customRules);
    }

    /**
     * Creates an engine loaded from the default YAML rule file
     * ({@value FuzzyRuleLoader#DEFAULT_RESOURCE_PATH}).
     *
     * <p>Use this factory method when reproducibility of the rule base is required:
     * the YAML file can be version-controlled, diff-reviewed, and cited as supplementary
     * material without needing to recompile the project.</p>
     *
     * @return engine backed by rules from {@code rca-rules.yaml}
     * @throws FuzzyRuleLoader.RuleLoadException if the YAML file is missing or invalid
     */
    public static MamdaniFuzzyRuleEngine fromYaml() {
        return new MamdaniFuzzyRuleEngine(FuzzyRuleLoader.loadDefault());
    }

    /**
     * Creates an engine loaded from a named classpath resource.
     *
     * @param resourcePath classpath-relative path to the YAML rule file
     * @return engine backed by rules from the given resource
     */
    public static MamdaniFuzzyRuleEngine fromYaml(String resourcePath) {
        return new MamdaniFuzzyRuleEngine(FuzzyRuleLoader.loadFromClasspath(resourcePath));
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * {@inheritDoc}
     *
     * <p>Runs the full Mamdani inference pipeline against {@code fuzzyVector} and
     * returns a {@link FaultHypothesis} with local confidence H and evidence trail.</p>
     */
    @Override
    public FaultHypothesis infer(FuzzyVector fuzzyVector) {
        Objects.requireNonNull(fuzzyVector, "fuzzyVector must not be null");

        // Step 1 – evaluate every rule
        Map<String, Double> ruleFireStrengths = new LinkedHashMap<>();
        for (FuzzyRule rule : ruleBase) {
            double alpha = rule.firingStrength(fuzzyVector);
            if (alpha > 0.0) {
                ruleFireStrengths.put(rule.getLabel(), alpha);
                log.debug("Rule '{}' fired with α={}", rule.getLabel(), alpha);
            }
        }

        if (ruleFireStrengths.isEmpty()) {
            log.debug("No rules fired for service '{}'", fuzzyVector.getServiceId());
            return buildZeroHypothesis(fuzzyVector.getServiceId());
        }

        // Step 2 – max-aggregate per fault category
        Map<String, Double> categoryStrengths = new LinkedHashMap<>();
        for (FuzzyRule rule : ruleBase) {
            double alpha = ruleFireStrengths.getOrDefault(rule.getLabel(), 0.0);
            if (alpha > 0.0) {
                categoryStrengths.merge(rule.getConsequentCategory(), alpha, Math::max);
            }
        }

        // Step 3 – dominant category (argmax) and global confidence (max)
        Map.Entry<String, Double> dominant = categoryStrengths.entrySet().stream()
                .max(Map.Entry.comparingByValue())
                .orElseThrow();

        double localConfidence = dominant.getValue();
        String dominantCategory = dominant.getKey();

        List<String> firedRuleLabels = ruleFireStrengths.keySet().stream()
                .sorted()
                .collect(Collectors.toList());

        log.debug("Service '{}': H={}, dominant='{}'",
                  fuzzyVector.getServiceId(), localConfidence, dominantCategory);

        return FaultHypothesis.builder()
                .serviceId(fuzzyVector.getServiceId())
                .localConfidence(localConfidence)
                .dominantFaultCategory(dominantCategory)
                .firedRules(firedRuleLabels)
                .ruleFireStrengths(ruleFireStrengths)
                .build();
    }

    // -----------------------------------------------------------------------
    // Rule base construction
    // -----------------------------------------------------------------------

    /**
     * Constructs the built-in expert rule base.
     * Rules follow the naming convention R{id}: {description}.
     * CFs are calibrated from published RCA benchmark studies.
     */
    private static List<FuzzyRule> buildDefaultRuleBase() {
        List<FuzzyRule> rules = new ArrayList<>();

        // ---- CPU_SATURATION rules ----------------------------------------
        rules.add(rule("R01: IF cpu_HIGH AND latency_ELEVATED THEN CPU_SATURATION",
                List.of("cpu_HIGH", "latency_ELEVATED"), "CPU_SATURATION", 0.85));

        rules.add(rule("R02: IF cpu_HIGH AND throughput_LOW THEN CPU_SATURATION",
                List.of("cpu_HIGH", "throughput_LOW"), "CPU_SATURATION", 0.80));

        rules.add(rule("R03: IF cpu_HIGH AND latency_CRITICAL THEN CPU_SATURATION",
                List.of("cpu_HIGH", "latency_CRITICAL"), "CPU_SATURATION", 0.92));

        // ---- MEMORY_PRESSURE rules ----------------------------------------
        rules.add(rule("R04: IF memory_HIGH AND throughput_LOW THEN MEMORY_PRESSURE",
                List.of("memory_HIGH", "throughput_LOW"), "MEMORY_PRESSURE", 0.80));

        rules.add(rule("R05: IF memory_HIGH AND latency_ELEVATED THEN MEMORY_PRESSURE",
                List.of("memory_HIGH", "latency_ELEVATED"), "MEMORY_PRESSURE", 0.75));

        rules.add(rule("R06: IF memory_HIGH AND cpu_MEDIUM THEN MEMORY_PRESSURE",
                List.of("memory_HIGH", "cpu_MEDIUM"), "MEMORY_PRESSURE", 0.70));

        // ---- SERVICE_ERROR rules ------------------------------------------
        rules.add(rule("R07: IF errorRate_HIGH THEN SERVICE_ERROR",
                List.of("errorRate_HIGH"), "SERVICE_ERROR", 0.90));

        rules.add(rule("R08: IF errorRate_ELEVATED AND latency_ELEVATED THEN SERVICE_ERROR",
                List.of("errorRate_ELEVATED", "latency_ELEVATED"), "SERVICE_ERROR", 0.78));

        rules.add(rule("R09: IF errorRate_ELEVATED AND cpu_HIGH THEN SERVICE_ERROR",
                List.of("errorRate_ELEVATED", "cpu_HIGH"), "SERVICE_ERROR", 0.72));

        // ---- LATENCY_ANOMALY rules ----------------------------------------
        rules.add(rule("R10: IF latency_CRITICAL THEN LATENCY_ANOMALY",
                List.of("latency_CRITICAL"), "LATENCY_ANOMALY", 0.88));

        rules.add(rule("R11: IF latency_ELEVATED AND throughput_LOW THEN LATENCY_ANOMALY",
                List.of("latency_ELEVATED", "throughput_LOW"), "LATENCY_ANOMALY", 0.74));

        // ---- CASCADING_FAILURE rules --------------------------------------
        rules.add(rule("R12: IF cpu_HIGH AND errorRate_ELEVATED AND latency_ELEVATED THEN CASCADING_FAILURE",
                List.of("cpu_HIGH", "errorRate_ELEVATED", "latency_ELEVATED"), "CASCADING_FAILURE", 0.92));

        rules.add(rule("R13: IF memory_HIGH AND errorRate_HIGH THEN CASCADING_FAILURE",
                List.of("memory_HIGH", "errorRate_HIGH"), "CASCADING_FAILURE", 0.87));

        rules.add(rule("R14: IF cpu_HIGH AND memory_HIGH AND latency_CRITICAL THEN CASCADING_FAILURE",
                List.of("cpu_HIGH", "memory_HIGH", "latency_CRITICAL"), "CASCADING_FAILURE", 0.95));

        // ---- RESOURCE_CONTENTION rules ------------------------------------
        rules.add(rule("R15: IF cpu_HIGH AND memory_HIGH THEN RESOURCE_CONTENTION",
                List.of("cpu_HIGH", "memory_HIGH"), "RESOURCE_CONTENTION", 0.82));

        rules.add(rule("R16: IF cpu_MEDIUM AND memory_HIGH AND throughput_LOW THEN RESOURCE_CONTENTION",
                List.of("cpu_MEDIUM", "memory_HIGH", "throughput_LOW"), "RESOURCE_CONTENTION", 0.68));

        // Note: NORMAL (healthy) is the absence of any fired fault rule, represented by H=0.
        // We do not add a NORMAL rule here because a low-confidence healthy service will
        // naturally produce zero firing strength across all FAULT rules, leaving H=0.

        return Collections.unmodifiableList(rules);
    }

    private static FuzzyRule rule(String label, List<String> antecedents,
                                  String consequent, double cf) {
        return FuzzyRule.builder()
                .label(label)
                .antecedents(List.copyOf(antecedents))
                .consequentCategory(consequent)
                .certaintyFactor(cf)
                .build();
    }

    private static FaultHypothesis buildZeroHypothesis(String serviceId) {
        return FaultHypothesis.builder()
                .serviceId(serviceId)
                .localConfidence(0.0)
                .dominantFaultCategory("UNKNOWN")
                .firedRules(List.of())
                .ruleFireStrengths(Map.of())
                .build();
    }

    /** Returns an unmodifiable view of the loaded rule base (useful for introspection). */
    public List<FuzzyRule> getRuleBase() { return ruleBase; }
}
