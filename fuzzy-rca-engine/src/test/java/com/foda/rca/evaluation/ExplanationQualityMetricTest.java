package com.foda.rca.evaluation;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tests for {@link ExplanationQualityMetric}. Verifies each sub-score's contract
 * independently, the arithmetic of the overall score, and edge cases (null/blank
 * input, healthy-baseline scenarios).
 */
@DisplayName("ExplanationQualityMetric")
class ExplanationQualityMetricTest {

    private static final double EPS = 1e-9;

    // ---------------------------------------------------------------------
    // Faithfulness
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("Faithfulness")
    class FaithfulnessTests {

        @Test
        @DisplayName("All ground-truth causes mentioned → 1.0")
        void allMentioned() {
            assertEquals(1.0,
                    ExplanationQualityMetric.faithfulness(
                            "the root cause is db-svc, the leaf dependency",
                            Set.of("db-svc")),
                    EPS);
        }

        @Test
        @DisplayName("No ground-truth cause mentioned → 0.0")
        void noneMentioned() {
            assertEquals(0.0,
                    ExplanationQualityMetric.faithfulness(
                            "the system appears to be running normally",
                            Set.of("db-svc")),
                    EPS);
        }

        @Test
        @DisplayName("Partial mention (1 of 2 causes) → 0.5")
        void partialMention() {
            assertEquals(0.5,
                    ExplanationQualityMetric.faithfulness(
                            "the cause is db-svc; payment-svc is healthy here",
                            Set.of("db-svc", "order-svc")),
                    EPS);
        }

        @Test
        @DisplayName("Empty truth set (S08 healthy baseline) → vacuous 1.0")
        void emptyTruth() {
            assertEquals(1.0,
                    ExplanationQualityMetric.faithfulness(
                            "no fault detected", Set.of()),
                    EPS);
        }

        @Test
        @DisplayName("Whole-word matching: 'db-svc-foo' does NOT count as 'db-svc' hit")
        void wholeWordOnly() {
            assertEquals(0.0,
                    ExplanationQualityMetric.faithfulness(
                            "see db-svc-foo for details", Set.of("db-svc")),
                    EPS);
        }

        @Test
        @DisplayName("Case-insensitive matching: 'DB-SVC' counts as hit for 'db-svc'")
        void caseInsensitive() {
            assertEquals(1.0,
                    ExplanationQualityMetric.faithfulness(
                            "see DB-SVC for details", Set.of("db-svc")),
                    EPS);
        }
    }

    // ---------------------------------------------------------------------
    // Coverage
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("Coverage")
    class CoverageTests {

        @Test
        @DisplayName("Complete path match → 1.0")
        void fullMatch() {
            String expl = "Causal propagation path: gateway → order-svc → db-svc.\n\nNext.";
            assertEquals(1.0,
                    ExplanationQualityMetric.coverage(expl,
                            List.of("gateway", "order-svc", "db-svc")),
                    EPS);
        }

        @Test
        @DisplayName("Subset of path present → fractional credit")
        void partialMatch() {
            String expl = "Causal propagation path: order-svc → db-svc.\n\nNext.";
            // Ground truth has 3 hops; explanation contains 2 of them in order.
            assertEquals(2.0 / 3.0,
                    ExplanationQualityMetric.coverage(expl,
                            List.of("gateway", "order-svc", "db-svc")),
                    EPS);
        }

        @Test
        @DisplayName("Empty actual path (S08) → vacuous 1.0")
        void emptyPath() {
            assertEquals(1.0,
                    ExplanationQualityMetric.coverage("any text", List.of()),
                    EPS);
        }

        @Test
        @DisplayName("No 'Causal propagation path:' paragraph → 0.0")
        void noPathParagraph() {
            assertEquals(0.0,
                    ExplanationQualityMetric.coverage(
                            "no relevant text here",
                            List.of("a", "b")),
                    EPS);
        }

        @Test
        @DisplayName("Wrong order → LCS-based partial credit")
        void wrongOrder() {
            // Reversed: ground-truth A→B→C, rendered C→B→A; LCS length over ordered pairs is 1.
            String expl = "Causal propagation path: c → b → a.\n\nNext.";
            assertEquals(1.0 / 3.0,
                    ExplanationQualityMetric.coverage(expl,
                            List.of("a", "b", "c")),
                    EPS);
        }

        @Test
        @DisplayName("Accepts ' -> ' separator as a fallback for ' → '")
        void asciiSeparator() {
            String expl = "Causal propagation path: gateway -> order-svc -> db-svc.\n\nNext.";
            assertEquals(1.0,
                    ExplanationQualityMetric.coverage(expl,
                            List.of("gateway", "order-svc", "db-svc")),
                    EPS);
        }
    }

    // ---------------------------------------------------------------------
    // Conciseness
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("Conciseness")
    class ConcisenessTests {

        @Test
        @DisplayName("No repetition → 1.0")
        void noRepetition() {
            assertEquals(1.0,
                    ExplanationQualityMetric.conciseness(
                            "alpha beta gamma delta epsilon zeta eta theta"),
                    EPS);
        }

        @Test
        @DisplayName("Up to two occurrences are free")
        void twoOccurrencesAllowed() {
            // every word appears exactly twice → no penalty
            assertEquals(1.0,
                    ExplanationQualityMetric.conciseness(
                            "alpha alpha beta beta gamma gamma"),
                    EPS);
        }

        @Test
        @DisplayName("Heavy repetition → < 0.5")
        void heavyRepetition() {
            // 'foo' repeats 10 times → 8 duplicates out of 10 tokens → score 0.2
            String s = "foo foo foo foo foo foo foo foo foo foo";
            double score = ExplanationQualityMetric.conciseness(s);
            assertTrue(score < 0.5, "expected heavy repetition to score below 0.5; got " + score);
            assertEquals(0.2, score, EPS);
        }

        @Test
        @DisplayName("Stop-words excluded: 'the the the the' is fully concise")
        void stopWordsIgnored() {
            assertEquals(1.0,
                    ExplanationQualityMetric.conciseness("the the the the of of of"),
                    EPS);
        }

        @Test
        @DisplayName("Empty / single-word inputs are vacuously concise (1.0)")
        void emptyAndSingleWord() {
            assertEquals(1.0, ExplanationQualityMetric.conciseness(""),     EPS);
            assertEquals(1.0, ExplanationQualityMetric.conciseness("foo"),  EPS);
        }
    }

    // ---------------------------------------------------------------------
    // SemanticGroundedness
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("SemanticGroundedness")
    class GroundednessTests {

        @Test
        @DisplayName("Legacy explanation (no diagnostic: prefix, with category labels) → 0.0")
        void legacy() {
            String legacy = "The dominant fault pattern is CPU_SATURATION. "
                          + "Apply the standard CPU_SATURATION remediation playbook.";
            assertEquals(0.0,
                    ExplanationQualityMetric.semanticGroundedness(legacy),
                    EPS);
        }

        @Test
        @DisplayName("Ontology explanation (diagnostic:CpuSaturation, no engine labels) → 1.0")
        void ontologyOnly() {
            String onto = "The dominant fault pattern is CPU Saturation (diagnostic:CpuSaturation). "
                        + "See diagnostic:Rec_CpuSaturation.";
            assertEquals(1.0,
                    ExplanationQualityMetric.semanticGroundedness(onto),
                    EPS);
        }

        @Test
        @DisplayName("Mixed: 1 diagnostic: + 2 category labels → 1/3")
        void mixed() {
            String mixed = "diagnostic:LatencySpike — see CPU_SATURATION and LATENCY_ANOMALY.";
            assertEquals(1.0 / 3.0,
                    ExplanationQualityMetric.semanticGroundedness(mixed),
                    EPS);
        }

        @Test
        @DisplayName("No technical entities of either kind → 0.5 (uninformative)")
        void uninformative() {
            assertEquals(0.5,
                    ExplanationQualityMetric.semanticGroundedness(
                            "the system is operating within expected parameters"),
                    EPS);
        }
    }

    // ---------------------------------------------------------------------
    // Overall + integration via evaluate()
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("evaluate() — overall score arithmetic")
    class EvaluateTests {

        private static final GroundTruthScenario SCENARIO_DB =
                GroundTruthScenario.builder()
                        .scenarioId("S01-test")
                        .scenarioName("DB_TEST")
                        .description("test")
                        .faultType("LATENCY_ANOMALY")
                        .observations(List.of())
                        .dependencyGraph(null)
                        .trueRootCauses(Set.of("db-svc"))
                        .build();

        @Test
        @DisplayName("Overall = mean of the four sub-scores")
        void overallIsMean() {
            String expl = "Service db-svc has a problem.\n\n"
                        + "Causal propagation path: gateway → order-svc → db-svc.\n\n"
                        + "diagnostic:LatencySpike applies here.";

            ExplanationScore s = ExplanationQualityMetric.evaluate(
                    expl, SCENARIO_DB, List.of("gateway", "order-svc", "db-svc"));

            double expected =
                    (s.getFaithfulness()
                            + s.getCoverage()
                            + s.getConciseness()
                            + s.getSemanticGroundedness()) / 4.0;
            assertEquals(expected, s.getOverall(), EPS);
            assertTrue(s.getFaithfulness() >= 0.0 && s.getFaithfulness() <= 1.0);
            assertTrue(s.getOverall()      >= 0.0 && s.getOverall()      <= 1.0);
        }

        @Test
        @DisplayName("Null explanation → all-zero score")
        void nullExplanation() {
            ExplanationScore s = ExplanationQualityMetric.evaluate(
                    null, SCENARIO_DB, List.of("gateway", "db-svc"));
            assertEquals(0.0, s.getFaithfulness(),         EPS);
            assertEquals(0.0, s.getCoverage(),             EPS);
            assertEquals(0.0, s.getConciseness(),          EPS);
            assertEquals(0.0, s.getSemanticGroundedness(), EPS);
            assertEquals(0.0, s.getOverall(),              EPS);
        }

        @Test
        @DisplayName("Blank explanation → all-zero score")
        void blankExplanation() {
            ExplanationScore s = ExplanationQualityMetric.evaluate(
                    "   \n\n   ", SCENARIO_DB, List.of("gateway", "db-svc"));
            assertEquals(0.0, s.getOverall(), EPS);
        }

        @Test
        @DisplayName("Single-word explanation produces valid in-range score (no NaN, no exception)")
        void singleWord() {
            ExplanationScore s = ExplanationQualityMetric.evaluate(
                    "db-svc", SCENARIO_DB, List.of("db-svc"));
            assertTrue(s.getOverall() >= 0.0 && s.getOverall() <= 1.0,
                    "overall must stay in [0,1]; got " + s.getOverall());
        }

        @Test
        @DisplayName("Null scenario → IllegalArgumentException")
        void nullScenario() {
            assertThrows(IllegalArgumentException.class,
                    () -> ExplanationQualityMetric.evaluate("text", null, List.of()));
        }

        @Test
        @DisplayName("Determinism: same inputs → identical scores across runs")
        void deterministic() {
            String expl = "Service db-svc.\n\n"
                        + "Causal propagation path: gateway → db-svc.\n\n"
                        + "diagnostic:LatencySpike";
            ExplanationScore a = ExplanationQualityMetric.evaluate(
                    expl, SCENARIO_DB, List.of("gateway", "db-svc"));
            ExplanationScore b = ExplanationQualityMetric.evaluate(
                    expl, SCENARIO_DB, List.of("gateway", "db-svc"));
            assertEquals(a.getOverall(), b.getOverall(), 0.0,
                    "metric must be deterministic");
            assertEquals(a.toString(), b.toString());
        }
    }

    // ---------------------------------------------------------------------
    // toString() format
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("ExplanationScore.toString prints all five values to 4 decimal places")
    void toStringFormat() {
        ExplanationScore s = ExplanationScore.builder()
                .faithfulness(0.5).coverage(1.0).conciseness(0.9)
                .semanticGroundedness(0.25).overall(0.6625)
                .build();
        assertEquals("F=0.5000 C=1.0000 N=0.9000 G=0.2500 O=0.6625", s.toString());
    }
}
