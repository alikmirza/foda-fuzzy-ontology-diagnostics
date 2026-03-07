package com.foda.rca.inference;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * Loads {@link FuzzyRule} instances from a YAML configuration file.
 *
 * <h2>Purpose</h2>
 *
 * <p>The rule base is the most important tunable component of FCP-RCA. Externalising it to
 * YAML (rather than hard-coding in Java) enables reproducible experimentation: domain experts
 * can adjust certainty factors or add new rules without recompiling the engine. The resulting
 * rule file is also directly citable as supplementary material in the paper.</p>
 *
 * <h2>Default rule file</h2>
 *
 * <p>The canonical rule file ships at
 * {@code src/main/resources/rca-rules.yaml} and is loaded from the classpath by
 * {@link #loadDefault()}. It contains 20 rules covering 8 fault categories including
 * the 16 original FCP-RCA rules plus 4 new rules for MEMORY_LEAK_TENDENCY and
 * DOWNSTREAM_DEPENDENCY_SLOWDOWN.</p>
 *
 * <h2>Schema</h2>
 *
 * <p>Each entry in the {@code rules} list must have the following fields:
 * <pre>
 *   - id:              R01                              # required, unique
 *     label:           "R01: IF cpu_HIGH AND …"         # required
 *     antecedents:     [cpu_HIGH, latency_ELEVATED]     # required; ≥ 1 entry
 *     consequent:      CPU_SATURATION                   # required
 *     certaintyFactor: 0.85                             # required; [0.0, 1.0]
 * </pre>
 * </p>
 *
 * <h2>Usage</h2>
 * <pre>
 *   // Load default rule base from classpath
 *   List&lt;FuzzyRule&gt; rules = FuzzyRuleLoader.loadDefault();
 *   FuzzyRuleEngine engine = new MamdaniFuzzyRuleEngine(rules);
 *
 *   // Load from a custom classpath resource
 *   List&lt;FuzzyRule&gt; custom = FuzzyRuleLoader.loadFromClasspath("my-rules.yaml");
 *
 *   // Load from an absolute URL (file system, S3, etc.)
 *   List&lt;FuzzyRule&gt; fromFile = FuzzyRuleLoader.loadFrom(new URL("file:/path/to/rules.yaml"));
 * </pre>
 *
 * <h2>Validation</h2>
 * <p>The loader validates that every rule has a non-empty antecedent list and a
 * certaintyFactor in (0, 1]. Validation failures throw {@link IllegalArgumentException}
 * with the offending rule's {@code id} in the message.</p>
 */
@Slf4j
public class FuzzyRuleLoader {

    /** Default rule file path on the classpath. */
    public static final String DEFAULT_RESOURCE_PATH = "rca-rules.yaml";

    private static final ObjectMapper YAML_MAPPER =
            new ObjectMapper(new YAMLFactory());

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Loads the default rule base from {@value DEFAULT_RESOURCE_PATH} on the classpath.
     *
     * @return immutable list of validated {@link FuzzyRule} objects
     * @throws RuleLoadException if the file is missing, malformed, or fails validation
     */
    public static List<FuzzyRule> loadDefault() {
        return loadFromClasspath(DEFAULT_RESOURCE_PATH);
    }

    /**
     * Loads rules from a named classpath resource.
     *
     * @param resourcePath path relative to the root of the classpath
     * @return immutable list of validated {@link FuzzyRule} objects
     * @throws RuleLoadException if the resource is not found or cannot be parsed
     */
    public static List<FuzzyRule> loadFromClasspath(String resourcePath) {
        Objects.requireNonNull(resourcePath, "resourcePath must not be null");
        InputStream is = FuzzyRuleLoader.class.getClassLoader()
                                              .getResourceAsStream(resourcePath);
        if (is == null)
            throw new RuleLoadException(
                "Rule file not found on classpath: " + resourcePath);
        try (is) {
            return parseAndValidate(is, resourcePath);
        } catch (IOException e) {
            throw new RuleLoadException("Failed to read rule file: " + resourcePath, e);
        }
    }

    /**
     * Loads rules from an arbitrary {@link URL} (file system, JAR entry, HTTP, etc.).
     *
     * @param url location of the YAML rule file
     * @return immutable list of validated {@link FuzzyRule} objects
     * @throws RuleLoadException if the URL cannot be opened or the content is invalid
     */
    public static List<FuzzyRule> loadFrom(URL url) {
        Objects.requireNonNull(url, "url must not be null");
        try (InputStream is = url.openStream()) {
            return parseAndValidate(is, url.toString());
        } catch (IOException e) {
            throw new RuleLoadException("Failed to load rules from URL: " + url, e);
        }
    }

    // -----------------------------------------------------------------------
    // Internal parsing
    // -----------------------------------------------------------------------

    private static List<FuzzyRule> parseAndValidate(InputStream is, String source) throws IOException {
        RuleDocument doc = YAML_MAPPER.readValue(is, RuleDocument.class);
        if (doc.getRules() == null || doc.getRules().isEmpty())
            throw new RuleLoadException("Rule file contains no rules: " + source);

        List<FuzzyRule> rules = doc.getRules().stream()
                .map(r -> toFuzzyRule(r, source))
                .collect(Collectors.toList());

        log.info("Loaded {} rules from '{}'", rules.size(), source);
        return List.copyOf(rules); // immutable
    }

    private static FuzzyRule toFuzzyRule(RuleDto dto, String source) {
        validate(dto, source);
        return FuzzyRule.builder()
                .label(dto.getLabel())
                .antecedents(List.copyOf(dto.getAntecedents()))
                .consequentCategory(dto.getConsequent())
                .certaintyFactor(dto.getCertaintyFactor())
                .build();
    }

    private static void validate(RuleDto dto, String source) {
        String ctx = "[" + source + ", rule " + dto.getId() + "]";
        if (dto.getId() == null || dto.getId().isBlank())
            throw new IllegalArgumentException(ctx + " rule id is required");
        if (dto.getLabel() == null || dto.getLabel().isBlank())
            throw new IllegalArgumentException(ctx + " label is required");
        if (dto.getAntecedents() == null || dto.getAntecedents().isEmpty())
            throw new IllegalArgumentException(ctx + " antecedents list must not be empty");
        if (dto.getConsequent() == null || dto.getConsequent().isBlank())
            throw new IllegalArgumentException(ctx + " consequent is required");
        if (dto.getCertaintyFactor() <= 0.0 || dto.getCertaintyFactor() > 1.0)
            throw new IllegalArgumentException(
                ctx + " certaintyFactor must be in (0, 1], got: " + dto.getCertaintyFactor());
    }

    // -----------------------------------------------------------------------
    // DTO classes (Jackson deserialization targets)
    // -----------------------------------------------------------------------

    /** Root YAML document. */
    @Data
    static class RuleDocument {
        private String      version;
        private String      description;
        private List<RuleDto> rules;
    }

    /** Per-rule YAML entry. */
    @Data
    static class RuleDto {
        private String       id;
        private String       label;
        private List<String> antecedents;
        private String       consequent;
        @JsonProperty("certaintyFactor")
        private double       certaintyFactor;
    }

    // -----------------------------------------------------------------------
    // Exception type
    // -----------------------------------------------------------------------

    /** Thrown when a rule file cannot be loaded or fails validation. */
    public static class RuleLoadException extends RuntimeException {
        public RuleLoadException(String message)                  { super(message); }
        public RuleLoadException(String message, Throwable cause) { super(message, cause); }
    }
}
