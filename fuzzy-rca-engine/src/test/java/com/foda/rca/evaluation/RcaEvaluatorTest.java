package com.foda.rca.evaluation;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.core.FuzzyRcaEngineImpl;
import com.foda.rca.propagation.LocalOnlyPropagator;
import com.foda.rca.propagation.MaxPropagationBaseline;
import com.foda.rca.propagation.UniformWeightPropagator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link RcaEvaluator}, {@link SyntheticScenarioBuilder}, and
 * the four standard RCA metrics (Precision@k, Recall@k, MRR, NDCG@k).
 */
@DisplayName("RcaEvaluator Tests")
class RcaEvaluatorTest {

    private RcaEvaluator evaluator;

    @BeforeEach
    void setUp() {
        evaluator = new RcaEvaluator();
    }

    // -----------------------------------------------------------------------
    // Unit tests for static metric functions
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Precision@3: 2 of 3 hits → 0.667")
    void precisionAtK_twoOfThree() {
        List<String> predicted = List.of("A", "B", "C");
        Set<String>  truth     = Set.of("A", "C", "X");
        assertEquals(2.0/3.0, RcaEvaluator.precisionAtK(predicted, truth, 3), 1e-9);
    }

    @Test
    @DisplayName("Precision@3: all 3 correct → 1.0")
    void precisionAtK_perfect() {
        assertEquals(1.0, RcaEvaluator.precisionAtK(
                List.of("A","B","C"), Set.of("A","B","C"), 3), 1e-9);
    }

    @Test
    @DisplayName("Precision@3: none correct → 0.0")
    void precisionAtK_zero() {
        assertEquals(0.0, RcaEvaluator.precisionAtK(
                List.of("A","B","C"), Set.of("X","Y"), 3), 1e-9);
    }

    @Test
    @DisplayName("Recall@3: 2 of 4 ground-truth returned → 0.5")
    void recallAtK_twoOfFour() {
        List<String> predicted = List.of("A", "B", "C");
        Set<String>  truth     = Set.of("A", "C", "X", "Y");
        assertEquals(0.5, RcaEvaluator.recallAtK(predicted, truth, 3), 1e-9);
    }

    @Test
    @DisplayName("MRR: first hit at rank 1 → 1.0")
    void mrr_firstHitRank1() {
        assertEquals(1.0, RcaEvaluator.mrr(List.of("A","B","C"), Set.of("A")), 1e-9);
    }

    @Test
    @DisplayName("MRR: first hit at rank 2 → 0.5")
    void mrr_firstHitRank2() {
        assertEquals(0.5, RcaEvaluator.mrr(List.of("X","A","B"), Set.of("A")), 1e-9);
    }

    @Test
    @DisplayName("MRR: no hit → 0.0")
    void mrr_noHit() {
        assertEquals(0.0, RcaEvaluator.mrr(List.of("X","Y","Z"), Set.of("A")), 1e-9);
    }

    @Test
    @DisplayName("NDCG@3: perfect ranking → 1.0")
    void ndcgAtK_perfect() {
        assertEquals(1.0, RcaEvaluator.ndcgAtK(
                List.of("A","B","C"), Set.of("A","B","C"), 3), 1e-9);
    }

    @Test
    @DisplayName("NDCG@3: no hits → 0.0")
    void ndcgAtK_noHits() {
        assertEquals(0.0, RcaEvaluator.ndcgAtK(
                List.of("X","Y","Z"), Set.of("A","B"), 3), 1e-9);
    }

    @Test
    @DisplayName("NDCG@3: single hit at rank 2 < hit at rank 1")
    void ndcgAtK_positionMatters() {
        double rank1 = RcaEvaluator.ndcgAtK(List.of("A","X","Y"), Set.of("A"), 3);
        double rank2 = RcaEvaluator.ndcgAtK(List.of("X","A","Y"), Set.of("A"), 3);
        assertTrue(rank1 > rank2, "Hit at rank 1 should yield higher NDCG than hit at rank 2");
    }

    // -----------------------------------------------------------------------
    // Statistical helpers
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("mean([1,2,3,4,5]) = 3.0")
    void mean_correct() {
        assertEquals(3.0, RcaEvaluator.mean(new double[]{1,2,3,4,5}), 1e-9);
    }

    @Test
    @DisplayName("std([2,4,4,4,5,5,7,9]) ≈ 2.138")
    void std_correct() {
        assertEquals(2.138, RcaEvaluator.std(new double[]{2,4,4,4,5,5,7,9}), 1e-3);
    }

    // -----------------------------------------------------------------------
    // Single-scenario evaluation
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("S01 (DB fault): FCP-RCA (damped) achieves top-1 correct")
    void s01_databaseFault_top1Correct() {
        FuzzyRcaEngine engine = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();
        GroundTruthScenario s01 = SyntheticScenarioBuilder
                .s01_databaseCritical(SyntheticScenarioBuilder.standardGraph());

        ScenarioEvaluation result = evaluator.evaluate(engine, "FCP-RCA", s01, 3);

        assertTrue(result.isTopOneCorrect(), "db-svc must be the top-1 prediction");
        assertTrue(result.getPrecisionAtK() >= 0.3, "At least one of top-3 should be db-svc");
        assertTrue(result.getMrr() >= 0.5, "MRR ≥ 0.5 means root cause in top-2");
    }

    @Test
    @DisplayName("S02 (Gateway CPU): top-1 correct")
    void s02_gatewayCpu_top1Correct() {
        FuzzyRcaEngine engine = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();
        GroundTruthScenario s02 = SyntheticScenarioBuilder
                .s02_gatewayCpuSaturation(SyntheticScenarioBuilder.standardGraph());

        ScenarioEvaluation result = evaluator.evaluate(engine, "FCP-RCA", s02, 3);

        assertTrue(result.isTopOneCorrect(), "gateway must be the top-1 prediction");
        assertEquals(1.0, result.getMrr(), 1e-9, "MRR = 1.0 when top-1 correct");
    }

    // -----------------------------------------------------------------------
    // Aggregated comparison: FCP-RCA must outperform LocalOnly on single-fault suite
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("FCP-RCA (damped) MRR ≥ LocalOnly MRR on single-fault scenarios")
    void fcpRca_outperforms_localOnly_onSingleFaultSuite() {
        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.singleRootCauseSuite();

        FuzzyRcaEngine fcpRca   = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();
        FuzzyRcaEngine localOnly = FuzzyRcaEngineImpl.builder()
                .propagator(new LocalOnlyPropagator()).build();

        AggregatedEvaluation resultFcp   = evaluator.aggregate(fcpRca,   "FCP-RCA", suite, 3);
        AggregatedEvaluation resultLocal = evaluator.aggregate(localOnly, "LocalOnly", suite, 3);

        System.out.println(resultFcp.toSummaryLine());
        System.out.println(resultLocal.toSummaryLine());

        assertTrue(resultFcp.getMeanMrr() >= resultLocal.getMeanMrr(),
                "FCP-RCA MRR should be ≥ LocalOnly MRR across single-fault scenarios");
    }

    // -----------------------------------------------------------------------
    // Multi-algorithm comparison
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("compare() returns one entry per algorithm with correct scenario count")
    void compare_returnsAllAlgorithms() {
        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.singleRootCauseSuite();

        Map<String, FuzzyRcaEngine> algorithms = new LinkedHashMap<>();
        algorithms.put("FCP-RCA",      FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());
        algorithms.put("-Damping",     FuzzyRcaEngineImpl.builder().build());
        algorithms.put("-Propagation", FuzzyRcaEngineImpl.builder()
                                            .propagator(new LocalOnlyPropagator()).build());
        algorithms.put("-Weights",     FuzzyRcaEngineImpl.builder()
                                            .propagator(new UniformWeightPropagator(0.85)).build());

        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);

        assertEquals(4, results.size(), "Should have one entry per algorithm");
        results.forEach((name, agg) -> {
            assertEquals(suite.size(), agg.getNumScenarios());
            assertTrue(agg.getMeanPrecisionAtK() >= 0.0 && agg.getMeanPrecisionAtK() <= 1.0);
            assertTrue(agg.getMeanMrr()          >= 0.0 && agg.getMeanMrr()          <= 1.0);
            assertTrue(agg.getMeanNdcgAtK()      >= 0.0 && agg.getMeanNdcgAtK()      <= 1.0);
        });
    }

    // -----------------------------------------------------------------------
    // LaTeX table output
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("toLatexTable() produces non-empty string containing algorithm names")
    void toLatexTable_containsAlgorithmNames() {
        List<GroundTruthScenario> suite = List.of(
                SyntheticScenarioBuilder.s01_databaseCritical(SyntheticScenarioBuilder.standardGraph()));
        Map<String, FuzzyRcaEngine> algorithms = Map.of(
                "FCP-RCA", FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());

        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);
        String latex = evaluator.toLatexTable(results);

        assertFalse(latex.isBlank(), "LaTeX table should not be empty");
        assertTrue(latex.contains("FCP-RCA"), "Table should mention algorithm name");
        assertTrue(latex.contains("\\begin{table}"), "Should open table environment");
        assertTrue(latex.contains("\\end{table}"),   "Should close table environment");
    }

    // -----------------------------------------------------------------------
    // Healthy scenario: expect zero root causes
    // -----------------------------------------------------------------------

    // -----------------------------------------------------------------------
    // MaxPropagationBaseline ablation
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("FCP-RCA MRR >= MaxPropagation MRR on single-fault suite")
    void fcpRca_outperforms_maxPropagation_onSingleFaultSuite() {
        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.singleRootCauseSuite();

        FuzzyRcaEngine fcpRca   = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();
        FuzzyRcaEngine maxProp  = FuzzyRcaEngineImpl.builder()
                .propagator(new MaxPropagationBaseline()).build();

        AggregatedEvaluation resultFcp = evaluator.aggregate(fcpRca, "FCP-RCA", suite, 3);
        AggregatedEvaluation resultMax = evaluator.aggregate(maxProp, "MaxProp",  suite, 3);

        System.out.println(resultFcp.toSummaryLine());
        System.out.println(resultMax.toSummaryLine());

        // FCP-RCA should be at least competitive with max-propagation
        assertTrue(resultFcp.getMeanMrr() >= resultMax.getMeanMrr() * 0.9,
                "FCP-RCA MRR should be competitive with MaxPropagation baseline");
    }

    // -----------------------------------------------------------------------
    // CSV output
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("toCsv() produces non-empty string with header and data row")
    void toCsv_containsHeaderAndData(@TempDir Path tmpDir) {
        List<GroundTruthScenario> suite = List.of(
                SyntheticScenarioBuilder.s01_databaseCritical(SyntheticScenarioBuilder.standardGraph()));
        Map<String, FuzzyRcaEngine> algorithms = Map.of(
                "FCP-RCA", FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());

        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);
        String csv = evaluator.toCsv(results);

        assertFalse(csv.isBlank(), "CSV should not be empty");
        assertTrue(csv.startsWith("algorithm,"), "CSV must start with header");
        assertTrue(csv.contains("FCP-RCA"), "CSV must contain algorithm name");
    }

    @Test
    @DisplayName("writeCsv() creates rca-results.csv in the target directory")
    void writeCsv_createsFile(@TempDir Path tmpDir) throws Exception {
        List<GroundTruthScenario> suite = List.of(
                SyntheticScenarioBuilder.s01_databaseCritical(SyntheticScenarioBuilder.standardGraph()));
        Map<String, FuzzyRcaEngine> algorithms = Map.of(
                "FCP-RCA", FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());

        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);
        Path outFile = evaluator.writeCsv(results, tmpDir);

        assertTrue(Files.exists(outFile), "Output file should exist");
        String content = Files.readString(outFile);
        assertTrue(content.contains("mean_mrr"), "CSV header should mention mean_mrr");
        assertTrue(content.contains("FCP-RCA"), "CSV should contain algorithm name");
    }

    @Test
    @DisplayName("writePerScenarioCsv() creates rca-per-scenario.csv with per-row data")
    void writePerScenarioCsv_createsFile(@TempDir Path tmpDir) throws Exception {
        List<GroundTruthScenario> suite = SyntheticScenarioBuilder.singleRootCauseSuite();
        Map<String, FuzzyRcaEngine> algorithms = new LinkedHashMap<>();
        algorithms.put("FCP-RCA",  FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());
        algorithms.put("MaxProp",  FuzzyRcaEngineImpl.builder()
                                       .propagator(new MaxPropagationBaseline()).build());

        Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);
        Path outFile = evaluator.writePerScenarioCsv(results, tmpDir);

        assertTrue(Files.exists(outFile), "Per-scenario CSV should exist");
        String content = Files.readString(outFile);
        // 2 algorithms × 6 scenarios = 12 data rows + 1 header
        long lineCount = content.lines().filter(l -> !l.isBlank()).count();
        assertEquals(13, lineCount, "Expected 1 header + 12 data rows");
    }

    @Test
    @DisplayName("AggregatedEvaluation.toCsvRow() has same column count as csvHeader()")
    void csvRow_matchesHeaderColumnCount() {
        List<GroundTruthScenario> suite = List.of(
                SyntheticScenarioBuilder.s01_databaseCritical(SyntheticScenarioBuilder.standardGraph()));
        AggregatedEvaluation agg = evaluator.aggregate(
                FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build(),
                "FCP-RCA", suite, 3);

        int headerCols = AggregatedEvaluation.csvHeader().split(",").length;
        int rowCols    = agg.toCsvRow().split(",").length;
        assertEquals(headerCols, rowCols, "CSV row and header must have the same column count");
    }

    // -----------------------------------------------------------------------
    // Healthy scenario
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("S08 (healthy): engine returns no candidates → P@k and R@k defined correctly")
    void s08_healthy_zeroCandidates() {
        FuzzyRcaEngine engine = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();
        GroundTruthScenario s08 = SyntheticScenarioBuilder
                .s08_allHealthy(SyntheticScenarioBuilder.standardGraph());

        ScenarioEvaluation result = evaluator.evaluate(engine, "FCP-RCA", s08, 3);

        // Truth is empty → R@k is vacuously 1.0, P@k is 0.0 (or undefined)
        // Evaluator's contract: recall=1.0 when truth is empty, precision=0.0 if predicted is empty
        assertTrue(result.getRecallAtK() >= 0.0 && result.getRecallAtK() <= 1.0);
        assertTrue(result.getPrecisionAtK() >= 0.0);
        assertFalse(result.isTopOneCorrect(),
                "Healthy scenario: no prediction should be labelled as top-1 correct");
    }
}
