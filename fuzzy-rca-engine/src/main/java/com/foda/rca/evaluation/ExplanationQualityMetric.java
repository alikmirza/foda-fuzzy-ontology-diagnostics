package com.foda.rca.evaluation;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Composite explanation-quality metric for graph-propagation diagnostic explanations.
 *
 * <p>This metric is the explanation-quality contribution of the FCP-RCA × OWL paper.
 * To our knowledge, no published microservice-RCA work defines this specific
 * four-component composite. Each component captures one quality dimension; the
 * overall score is the unweighted mean.</p>
 *
 * <h2>Components</h2>
 * <ol>
 *   <li><strong>Faithfulness</strong> — does the explanation actually mention the
 *       ground-truth root cause? 1.0 if every {@link GroundTruthScenario#getTrueRootCauses()
 *       true cause} appears as a whole-word, case-insensitive substring; 0.5 if at least
 *       one but not all appear; 0.0 otherwise. Vacuously 1.0 when the truth set is empty
 *       (healthy baseline).</li>
 *   <li><strong>Coverage</strong> — does the rendered "Causal propagation path" paragraph
 *       reproduce the actual ground-truth path? Computed as the fraction of services in the
 *       ground-truth path that appear in the explanation's reported path <em>in correct
 *       order</em> (longest common subsequence over service-name positions). Vacuously 1.0
 *       when the ground-truth path is empty (healthy baseline) or unavailable.</li>
 *   <li><strong>Conciseness</strong> — penalises redundancy without penalising legitimate
 *       reuse of technical terms. {@code 1 − Σ_w max(0, count(w) − 2) / Σ_w count(w)} over
 *       case-folded, non-stop-word tokens. Floored at 0.</li>
 *   <li><strong>SemanticGroundedness</strong> — fraction of technical entities mentioned in
 *       the explanation that are backed by an OWL IRI. Counts substring matches of
 *       {@code "diagnostic:"} as grounded entities and substring matches of the engine-level
 *       fault category labels ({@code CPU_SATURATION}, {@code LATENCY_ANOMALY}, …) as
 *       ungrounded. {@code score = grounded / (grounded + ungrounded)}, with a 0.5 fallback
 *       when no technical entity of either kind is present (uninformative).</li>
 * </ol>
 *
 * <h2>Aggregation policy</h2>
 * <p>The overall score is the <em>unweighted</em> mean of the four components. We explicitly
 * avoid weighting because the components are conceptually orthogonal and any weight choice
 * would require empirical calibration that the FODA-12 benchmark cannot supply on its own.
 * Authors using this metric in derivative work should justify any deviation from equal
 * weighting.</p>
 *
 * <h2>Determinism</h2>
 * <p>This implementation has no randomness, no I/O, no Locale-dependent comparisons (we use
 * {@link java.util.Locale#ROOT} for case folding), and no map-iteration-order dependence
 * — running the metric twice on identical inputs produces identical outputs.</p>
 *
 * <h2>Output range</h2>
 * <p>Each sub-score is clamped into [0, 1] before being returned, so downstream consumers
 * never see invalid scores even on adversarial inputs.</p>
 */
public final class ExplanationQualityMetric {

    // ---------------------------------------------------------------------
    // Stop-word list (~50 English stop-words; standard short list, sufficient
    // for the kind of technical prose produced by the explanation builders)
    // ---------------------------------------------------------------------
    private static final Set<String> STOP_WORDS = new HashSet<>(Arrays.asList(
            "a", "an", "and", "are", "as", "at",
            "be", "but", "by",
            "for", "from",
            "has", "have", "he", "her", "his",
            "i", "in", "is", "it", "its",
            "of", "on", "or",
            "she", "so",
            "than", "that", "the", "their", "them", "then", "there", "these",
            "they", "this", "to",
            "was", "we", "were", "what", "when", "which", "who", "why", "will",
            "with",
            "you", "your"));

    // ---------------------------------------------------------------------
    // Engine fault-category labels treated as ungrounded entities
    // (the legacy NaturalLanguageExplanationBuilder emits these as plain strings)
    // ---------------------------------------------------------------------
    private static final List<String> FAULT_CATEGORY_LABELS = List.of(
            "CPU_SATURATION",
            "LATENCY_ANOMALY",
            "MEMORY_PRESSURE",
            "SERVICE_ERROR",
            "RESOURCE_CONTENTION",
            "CASCADING_FAILURE",
            "NORMAL",
            "UNKNOWN");

    private static final Pattern WORD_PATTERN = Pattern.compile("[A-Za-z][A-Za-z0-9_-]*");
    private static final Pattern PATH_LINE_PATTERN =
            Pattern.compile("Causal propagation path:\\s*(.*?)(?:\\n\\n|$)", Pattern.DOTALL);

    /**
     * Public no-arg constructor: this class has no per-instance state, but accepting an
     * instance at the {@link RcaEvaluator} boundary lets callers express "score
     * explanations" as a typed dependency rather than a magic boolean. The static
     * {@link #evaluate(String, GroundTruthScenario, java.util.List)} entry point remains
     * the single source of truth for scoring logic.
     */
    public ExplanationQualityMetric() { /* no per-instance state */ }

    // ---------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------

    /**
     * Score an explanation against a ground-truth scenario.
     *
     * @param explanation       the explanation text produced by an
     *                          {@link com.foda.rca.explanation.ExplanationBuilder}.
     *                          {@code null} or blank yields all-zero scores (overall = 0.0).
     * @param scenario          the ground-truth scenario (cause set, fault type, topology).
     *                          Must be non-null.
     * @param actualCausalPath  the engine's reported causal path for this prediction (used
     *                          only by the Coverage component — pass {@link List#of()} when
     *                          unavailable, in which case Coverage is awarded the vacuous
     *                          1.0 score).
     */
    public static ExplanationScore evaluate(String explanation,
                                            GroundTruthScenario scenario,
                                            List<String> actualCausalPath) {
        if (scenario == null) {
            throw new IllegalArgumentException("scenario must not be null");
        }
        if (explanation == null || explanation.isBlank()) {
            return ExplanationScore.builder()
                    .faithfulness(0.0).coverage(0.0).conciseness(0.0)
                    .semanticGroundedness(0.0).overall(0.0).build();
        }
        if (actualCausalPath == null) actualCausalPath = List.of();

        double f = clamp(faithfulness(explanation, scenario.getTrueRootCauses()));
        double c = clamp(coverage(explanation, actualCausalPath));
        double n = clamp(conciseness(explanation));
        double g = clamp(semanticGroundedness(explanation));
        double o = clamp((f + c + n + g) / 4.0);

        return ExplanationScore.builder()
                .faithfulness(f).coverage(c).conciseness(n)
                .semanticGroundedness(g).overall(o).build();
    }

    // ---------------------------------------------------------------------
    // 1. Faithfulness
    // ---------------------------------------------------------------------

    static double faithfulness(String explanation, Set<String> trueRootCauses) {
        if (trueRootCauses == null || trueRootCauses.isEmpty()) {
            // Healthy-baseline scenario: no cause to mention.
            return 1.0;
        }
        int hits = 0;
        for (String cause : trueRootCauses) {
            if (containsWholeWord(explanation, cause)) hits++;
        }
        if (hits == 0)                    return 0.0;
        if (hits == trueRootCauses.size()) return 1.0;
        return 0.5;
    }

    /**
     * Whole-word, case-insensitive substring search. Word boundaries are characters
     * not in {@code [A-Za-z0-9_-]} (so "db-svc" matches as a single token).
     */
    static boolean containsWholeWord(String haystack, String needle) {
        if (needle == null || needle.isEmpty()) return false;
        Pattern p = Pattern.compile(
                "(^|[^A-Za-z0-9_-])"
                        + Pattern.quote(needle)
                        + "($|[^A-Za-z0-9_-])",
                Pattern.CASE_INSENSITIVE);
        return p.matcher(haystack).find();
    }

    // ---------------------------------------------------------------------
    // 2. Coverage
    // ---------------------------------------------------------------------

    static double coverage(String explanation, List<String> actualCausalPath) {
        if (actualCausalPath == null || actualCausalPath.isEmpty()) {
            // Healthy baseline / no path available: vacuous full credit.
            return 1.0;
        }
        List<String> rendered = parseRenderedPath(explanation);
        if (rendered.isEmpty()) {
            return 0.0;
        }
        // Order-preserving fraction = LCS(actual, rendered).length / actual.length
        int lcs = longestCommonSubsequenceLength(actualCausalPath, rendered);
        return (double) lcs / actualCausalPath.size();
    }

    /** Extracts the service names rendered after "Causal propagation path:" in the explanation. */
    static List<String> parseRenderedPath(String explanation) {
        Matcher m = PATH_LINE_PATTERN.matcher(explanation);
        if (!m.find()) return List.of();
        String body = m.group(1).trim();
        // Truncate at the first sentence terminator to avoid pulling in trailing prose
        // ("foo → bar.  Upstream propagation contributed ..." → "foo → bar")
        int dot = body.indexOf('.');
        if (dot >= 0) body = body.substring(0, dot);
        // Engine renders with "→"; tests and external producers may use "->"
        String[] parts = body.split("\\s*(?:→|->)\\s*");
        java.util.ArrayList<String> out = new java.util.ArrayList<>(parts.length);
        for (String p : parts) {
            String trimmed = p.trim();
            if (!trimmed.isEmpty()) out.add(trimmed);
        }
        return out;
    }

    static int longestCommonSubsequenceLength(List<String> a, List<String> b) {
        int n = a.size(), m = b.size();
        int[][] dp = new int[n + 1][m + 1];
        for (int i = 1; i <= n; i++) {
            String ai = a.get(i - 1);
            for (int j = 1; j <= m; j++) {
                if (ai.equalsIgnoreCase(b.get(j - 1))) {
                    dp[i][j] = dp[i - 1][j - 1] + 1;
                } else {
                    dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
                }
            }
        }
        return dp[n][m];
    }

    // ---------------------------------------------------------------------
    // 3. Conciseness
    // ---------------------------------------------------------------------

    static double conciseness(String explanation) {
        Map<String, Integer> counts = new HashMap<>();
        Matcher m = WORD_PATTERN.matcher(explanation);
        while (m.find()) {
            String w = m.group().toLowerCase(java.util.Locale.ROOT);
            if (STOP_WORDS.contains(w)) continue;
            counts.merge(w, 1, Integer::sum);
        }
        int total = 0;
        int duplicates = 0;
        for (int c : counts.values()) {
            total      += c;
            duplicates += Math.max(0, c - 2);
        }
        if (total == 0) return 1.0; // no scoreable words: vacuously concise
        double s = 1.0 - ((double) duplicates / total);
        return Math.max(0.0, s);
    }

    // ---------------------------------------------------------------------
    // 4. SemanticGroundedness
    // ---------------------------------------------------------------------

    static double semanticGroundedness(String explanation) {
        // Grounded entities: occurrences of the OWL prefix "diagnostic:"
        int grounded = countOccurrences(explanation, "diagnostic:");

        // Ungrounded entities: occurrences of engine-level fault category labels
        // (whole-word, case-sensitive — these labels are upper-snake-case identifiers)
        int ungrounded = 0;
        for (String label : FAULT_CATEGORY_LABELS) {
            ungrounded += countWholeWord(explanation, label);
        }

        int total = grounded + ungrounded;
        if (total == 0) {
            // No technical entity of either kind: uninformative explanation.
            return 0.5;
        }
        return (double) grounded / total;
    }

    static int countOccurrences(String haystack, String needle) {
        if (needle.isEmpty()) return 0;
        int count = 0, idx = 0;
        while ((idx = haystack.indexOf(needle, idx)) != -1) {
            count++;
            idx += needle.length();
        }
        return count;
    }

    static int countWholeWord(String haystack, String needle) {
        Pattern p = Pattern.compile(
                "(^|[^A-Za-z0-9_-])"
                        + Pattern.quote(needle)
                        + "($|[^A-Za-z0-9_-])");
        Matcher m = p.matcher(haystack);
        int count = 0;
        while (m.find()) {
            count++;
        }
        return count;
    }

    // ---------------------------------------------------------------------
    // Utilities
    // ---------------------------------------------------------------------

    private static double clamp(double v) {
        if (Double.isNaN(v)) return 0.0;
        if (v < 0.0) return 0.0;
        if (v > 1.0) return 1.0;
        return v;
    }
}
