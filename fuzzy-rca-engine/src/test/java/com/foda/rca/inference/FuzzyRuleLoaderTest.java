package com.foda.rca.inference;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link FuzzyRuleLoader} and the canonical {@code rca-rules.yaml} rule file.
 */
@DisplayName("FuzzyRuleLoader Tests")
class FuzzyRuleLoaderTest {

    // -----------------------------------------------------------------------
    // Default YAML file loading
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("loadDefault() loads rca-rules.yaml and returns non-empty list")
    void loadDefault_returnsNonEmptyList() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        assertFalse(rules.isEmpty(), "Default rule file must contain at least one rule");
    }

    @Test
    @DisplayName("loadDefault() loads at least 20 rules (16 original + 4 new)")
    void loadDefault_containsAllExpectedRules() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        assertTrue(rules.size() >= 20,
                "Expected at least 20 rules, got " + rules.size());
    }

    @Test
    @DisplayName("loadDefault() includes all 6 original fault categories")
    void loadDefault_coversAllOriginalCategories() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        List<String> categories = rules.stream()
                .map(FuzzyRule::getConsequentCategory)
                .distinct().toList();
        assertTrue(categories.contains("CPU_SATURATION"),        "Missing CPU_SATURATION");
        assertTrue(categories.contains("MEMORY_PRESSURE"),       "Missing MEMORY_PRESSURE");
        assertTrue(categories.contains("SERVICE_ERROR"),         "Missing SERVICE_ERROR");
        assertTrue(categories.contains("LATENCY_ANOMALY"),       "Missing LATENCY_ANOMALY");
        assertTrue(categories.contains("CASCADING_FAILURE"),     "Missing CASCADING_FAILURE");
        assertTrue(categories.contains("RESOURCE_CONTENTION"),   "Missing RESOURCE_CONTENTION");
    }

    @Test
    @DisplayName("loadDefault() includes new MEMORY_LEAK_TENDENCY category")
    void loadDefault_includesMemoryLeakTendency() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        assertTrue(rules.stream()
                .anyMatch(r -> "MEMORY_LEAK_TENDENCY".equals(r.getConsequentCategory())),
                "MEMORY_LEAK_TENDENCY rules should be present");
    }

    @Test
    @DisplayName("loadDefault() includes new DOWNSTREAM_DEPENDENCY_SLOWDOWN category")
    void loadDefault_includesDownstreamDependencySlowdown() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        assertTrue(rules.stream()
                .anyMatch(r -> "DOWNSTREAM_DEPENDENCY_SLOWDOWN".equals(r.getConsequentCategory())),
                "DOWNSTREAM_DEPENDENCY_SLOWDOWN rules should be present");
    }

    @Test
    @DisplayName("All loaded rules have valid certaintyFactor in (0, 1]")
    void loadDefault_allCFsValid() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        rules.forEach(r -> assertTrue(
                r.getCertaintyFactor() > 0.0 && r.getCertaintyFactor() <= 1.0,
                "Invalid CF=" + r.getCertaintyFactor() + " for rule: " + r.getLabel()));
    }

    @Test
    @DisplayName("All loaded rules have non-empty antecedent lists")
    void loadDefault_allAntecedentsNonEmpty() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        rules.forEach(r -> assertFalse(r.getAntecedents().isEmpty(),
                "Empty antecedents for rule: " + r.getLabel()));
    }

    @Test
    @DisplayName("All loaded rules have non-blank labels")
    void loadDefault_allLabelsNonBlank() {
        List<FuzzyRule> rules = FuzzyRuleLoader.loadDefault();
        rules.forEach(r -> assertFalse(r.getLabel() == null || r.getLabel().isBlank(),
                "Blank label for a rule"));
    }

    // -----------------------------------------------------------------------
    // MamdaniFuzzyRuleEngine.fromYaml() integration
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("MamdaniFuzzyRuleEngine.fromYaml() creates a functional engine")
    void fromYaml_createsValidEngine() {
        MamdaniFuzzyRuleEngine engine = MamdaniFuzzyRuleEngine.fromYaml();
        assertNotNull(engine);
        assertFalse(engine.getRuleBase().isEmpty());
    }

    @Test
    @DisplayName("YAML-loaded engine has more rules than hard-coded baseline (20 vs 16)")
    void fromYaml_hasMoreRulesThanHardCoded() {
        MamdaniFuzzyRuleEngine yamlEngine   = MamdaniFuzzyRuleEngine.fromYaml();
        MamdaniFuzzyRuleEngine defaultEngine = new MamdaniFuzzyRuleEngine();

        assertTrue(yamlEngine.getRuleBase().size() > defaultEngine.getRuleBase().size(),
                "YAML engine should have more rules (20) than built-in (16)");
    }

    // -----------------------------------------------------------------------
    // Error handling
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("loadFromClasspath() throws RuleLoadException for missing resource")
    void loadFromClasspath_missingFile_throwsRuleLoadException() {
        assertThrows(FuzzyRuleLoader.RuleLoadException.class,
                () -> FuzzyRuleLoader.loadFromClasspath("non-existent-rules.yaml"));
    }
}
