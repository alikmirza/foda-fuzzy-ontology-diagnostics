package com.foda.rca.evaluation;

import com.foda.rca.explanation.ExplanationBuilder;
import com.foda.rca.explanation.NaturalLanguageExplanationBuilder;
import com.foda.rca.explanation.OntologyGroundedExplanationBuilder;
import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.RankedCause;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.PrintWriter;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Overhead measurement for the ontology-grounded explanation layer.
 *
 * <p>Answers reviewer comment 6 ("the claim of zero overhead should be softened unless
 * supported by runtime and memory measurements") by measuring, for both explanation
 * builders:</p>
 *
 * <ol>
 *   <li><strong>Startup cost</strong> — wall-clock time to construct the builder, which for
 *       the ontology-grounded builder includes loading {@code DiagnosticKB.owl} into a Jena
 *       {@code OntModel} and running the SPARQL bundle once per fault category.</li>
 *   <li><strong>Retained heap</strong> — steady-state bytes held by one live builder
 *       instance after the transient Jena model has been collected.</li>
 *   <li><strong>Per-explanation latency</strong> — mean and percentile nanoseconds per
 *       {@code explain()} call on the runtime hot path.</li>
 *   <li><strong>Per-explanation allocation</strong> — bytes allocated per {@code explain()}
 *       call, read from the HotSpot thread allocation counter. This is the most stable of
 *       the four numbers because it does not depend on machine load.</li>
 * </ol>
 *
 * <p><strong>Methodological caveat, to be reported alongside the numbers.</strong> This is a
 * single-JVM harness, not JMH: it applies a warm-up but does not fork, does not control for
 * JIT profile pollution between the two builders, and does not run the builders in separate
 * JVMs. The latency figures are therefore indicative rather than publication-grade in
 * isolation; the allocation figures and the retained-heap figure are robust. For a headline
 * claim in the paper, report the allocation delta and the order of magnitude of the latency
 * delta, and state the harness used.</p>
 *
 * <p>Writes {@code target/explanation-overhead.csv} and prints a console summary.</p>
 */
@DisplayName("Explanation-layer overhead (runtime and memory)")
public class ExplanationOverheadBenchmarkTest {

    /** Fault categories exercised, matching the engine's six-value vocabulary. */
    private static final List<String> CATEGORIES = List.of(
            "CPU_SATURATION", "LATENCY_ANOMALY", "MEMORY_PRESSURE",
            "SERVICE_ERROR", "RESOURCE_CONTENTION", "CASCADING_FAILURE");

    private static final int STARTUP_REPS   = 10;
    private static final int RETAINED_REPS  = 20;
    private static final int WARMUP_CALLS   = 50_000;
    private static final int MEASURE_BATCH  = 20_000;
    private static final int MEASURE_ROUNDS = 30;

    /** Consumes results so the JIT cannot eliminate the calls. */
    private static long sink;

    @Test
    void measureOverheadAndExportCsv() throws IOException {
        List<RankedCause>     causes      = new ArrayList<>();
        List<FuzzyVector>     vectors     = new ArrayList<>();
        List<FaultHypothesis> hypotheses  = new ArrayList<>();
        for (String c : CATEGORIES) {
            causes.add(rankedCause("db-svc", c));
            vectors.add(vector("db-svc"));
            hypotheses.add(hypothesis("db-svc", c));
        }

        Map<String, Result> results = new LinkedHashMap<>();

        // ---- 1. startup cost ------------------------------------------------
        double baselineStartupMs = timeConstruction(NaturalLanguageExplanationBuilder::new);
        double ontologyStartupMs = timeConstruction(OntologyGroundedExplanationBuilder::new);

        // ---- 2. retained heap ----------------------------------------------
        long baselineRetained = retainedBytes(NaturalLanguageExplanationBuilder::new);
        long ontologyRetained = retainedBytes(OntologyGroundedExplanationBuilder::new);

        // ---- 3 & 4. latency and allocation ---------------------------------
        ExplanationBuilder baseline = new NaturalLanguageExplanationBuilder();
        ExplanationBuilder ontology = new OntologyGroundedExplanationBuilder();

        // Interleaved warm-up so both builders reach the same JIT state.
        for (int i = 0; i < WARMUP_CALLS; i++) {
            int k = i % CATEGORIES.size();
            sink += baseline.explain(causes.get(k), vectors.get(k), hypotheses.get(k)).length();
            sink += ontology.explain(causes.get(k), vectors.get(k), hypotheses.get(k)).length();
        }

        double[] baselineNs = latencyRounds(baseline, causes, vectors, hypotheses);
        double[] ontologyNs = latencyRounds(ontology, causes, vectors, hypotheses);

        long baselineAlloc = allocationPerCall(baseline, causes, vectors, hypotheses);
        long ontologyAlloc = allocationPerCall(ontology, causes, vectors, hypotheses);

        results.put("Baseline (template)", new Result(
                baselineStartupMs, baselineRetained, mean(baselineNs),
                percentile(baselineNs, 50), percentile(baselineNs, 95), baselineAlloc));
        results.put("Ontology-Grounded", new Result(
                ontologyStartupMs, ontologyRetained, mean(ontologyNs),
                percentile(ontologyNs, 50), percentile(ontologyNs, 95), ontologyAlloc));

        printSummary(results);
        Path out = Path.of("target", "explanation-overhead.csv");
        writeCsv(results, out);

        assertTrue(Files.exists(out), "explanation-overhead.csv must be written");
        assertTrue(sink != Long.MIN_VALUE, "sink keeps the JIT honest");
    }

    // ------------------------------------------------------------------ steps

    private static double timeConstruction(java.util.function.Supplier<ExplanationBuilder> ctor) {
        ExplanationBuilder warm = ctor.get();          // warm classloading and Jena init
        sink += warm.hashCode();
        long[] ns = new long[STARTUP_REPS];
        for (int i = 0; i < STARTUP_REPS; i++) {
            long t0 = System.nanoTime();
            ExplanationBuilder b = ctor.get();
            long t1 = System.nanoTime();
            sink += b.hashCode();
            ns[i] = t1 - t0;
        }
        Arrays.sort(ns);
        return ns[ns.length / 2] / 1_000_000.0;        // median, in milliseconds
    }

    private static long retainedBytes(java.util.function.Supplier<ExplanationBuilder> ctor) {
        settle();
        long before = usedHeap();
        ExplanationBuilder[] held = new ExplanationBuilder[RETAINED_REPS];
        for (int i = 0; i < RETAINED_REPS; i++) {
            held[i] = ctor.get();
        }
        settle();                                       // drop the transient Jena models
        long after = usedHeap();
        sink += held[0].hashCode();                     // keep the array reachable
        long delta = after - before;
        return delta <= 0 ? 0 : delta / RETAINED_REPS;
    }

    private static double[] latencyRounds(ExplanationBuilder b,
                                          List<RankedCause> causes,
                                          List<FuzzyVector> vectors,
                                          List<FaultHypothesis> hypotheses) {
        double[] perRound = new double[MEASURE_ROUNDS];
        for (int r = 0; r < MEASURE_ROUNDS; r++) {
            long t0 = System.nanoTime();
            for (int i = 0; i < MEASURE_BATCH; i++) {
                int k = i % CATEGORIES.size();
                sink += b.explain(causes.get(k), vectors.get(k), hypotheses.get(k)).length();
            }
            long t1 = System.nanoTime();
            perRound[r] = (double) (t1 - t0) / MEASURE_BATCH;
        }
        return perRound;
    }

    private static long allocationPerCall(ExplanationBuilder b,
                                          List<RankedCause> causes,
                                          List<FuzzyVector> vectors,
                                          List<FaultHypothesis> hypotheses) {
        java.lang.management.ThreadMXBean raw = ManagementFactory.getThreadMXBean();
        if (!(raw instanceof com.sun.management.ThreadMXBean bean) || !bean.isThreadAllocatedMemorySupported()) {
            return -1;                                  // not a HotSpot JVM; reported as n/a
        }
        bean.setThreadAllocatedMemoryEnabled(true);
        final int calls = MEASURE_BATCH;
        long a0 = bean.getCurrentThreadAllocatedBytes();
        for (int i = 0; i < calls; i++) {
            int k = i % CATEGORIES.size();
            sink += b.explain(causes.get(k), vectors.get(k), hypotheses.get(k)).length();
        }
        long a1 = bean.getCurrentThreadAllocatedBytes();
        return (a1 - a0) / calls;
    }

    // ------------------------------------------------------------------ utils

    private static void settle() {
        for (int i = 0; i < 4; i++) {
            System.gc();
            try {
                Thread.sleep(60);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private static long usedHeap() {
        Runtime rt = Runtime.getRuntime();
        return rt.totalMemory() - rt.freeMemory();
    }

    private static double mean(double[] xs) {
        double s = 0;
        for (double x : xs) {
            s += x;
        }
        return s / xs.length;
    }

    private static double percentile(double[] xs, int p) {
        double[] c = xs.clone();
        Arrays.sort(c);
        int idx = (int) Math.ceil(p / 100.0 * c.length) - 1;
        return c[Math.max(0, Math.min(idx, c.length - 1))];
    }

    private record Result(double startupMs, long retainedBytes, double meanNs,
                          double p50Ns, double p95Ns, long allocBytes) {}

    private static void printSummary(Map<String, Result> results) {
        Result base = results.get("Baseline (template)");
        Result onto = results.get("Ontology-Grounded");
        System.out.println();
        System.out.println("==========================================================================================");
        System.out.println(" Explanation-layer overhead  (single-JVM harness, not JMH — see class Javadoc)");
        System.out.println("==========================================================================================");
        System.out.printf("%-22s %12s %14s %12s %12s %14s%n",
                "Builder", "startup ms", "retained B", "mean ns", "p95 ns", "alloc B/call");
        System.out.println("------------------------------------------------------------------------------------------");
        for (Map.Entry<String, Result> e : results.entrySet()) {
            Result r = e.getValue();
            System.out.printf("%-22s %12.2f %14d %12.1f %12.1f %14s%n",
                    e.getKey(), r.startupMs(), r.retainedBytes(), r.meanNs(), r.p95Ns(),
                    r.allocBytes() < 0 ? "n/a" : Long.toString(r.allocBytes()));
        }
        System.out.println("------------------------------------------------------------------------------------------");
        System.out.printf(" Delta: startup %+.2f ms, retained %+d B, mean latency %+.1f ns (%.2fx), alloc %+d B/call%n",
                onto.startupMs() - base.startupMs(),
                onto.retainedBytes() - base.retainedBytes(),
                onto.meanNs() - base.meanNs(),
                base.meanNs() == 0 ? 0 : onto.meanNs() / base.meanNs(),
                onto.allocBytes() < 0 || base.allocBytes() < 0 ? 0 : onto.allocBytes() - base.allocBytes());
        System.out.println("==========================================================================================");
        System.out.println(" JVM: " + System.getProperty("java.vm.name") + " " + System.getProperty("java.version"));
        System.out.println(" OS : " + System.getProperty("os.name") + " " + System.getProperty("os.arch")
                + ", " + Runtime.getRuntime().availableProcessors() + " cores");
        System.out.println("==========================================================================================");
    }

    private static void writeCsv(Map<String, Result> results, Path out) throws IOException {
        Files.createDirectories(out.getParent());
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(out, StandardCharsets.UTF_8))) {
            pw.println("builder,startup_ms_median,retained_bytes_per_instance,"
                    + "latency_mean_ns,latency_p50_ns,latency_p95_ns,alloc_bytes_per_call");
            for (Map.Entry<String, Result> e : results.entrySet()) {
                Result r = e.getValue();
                pw.printf("%s,%.3f,%d,%.2f,%.2f,%.2f,%d%n",
                        e.getKey(), r.startupMs(), r.retainedBytes(),
                        r.meanNs(), r.p50Ns(), r.p95Ns(), r.allocBytes());
            }
        }
        System.out.println(" CSV: " + out.toAbsolutePath());
    }

    // ---------------------------------------------------------------- fixtures

    private static RankedCause rankedCause(String svc, String category) {
        return RankedCause.builder()
                .rank(1)
                .serviceId(svc)
                .finalConfidence(0.87)
                .localConfidence(0.74)
                .propagatedConfidence(0.13)
                .faultCategory(category)
                .causalPath(List.of("gateway", "order-svc", svc))
                .build();
    }

    private static FuzzyVector vector(String svc) {
        return FuzzyVector.builder()
                .serviceId(svc)
                .memberships(Map.of(
                        "cpu_HIGH",         0.82,
                        "latency_CRITICAL", 0.91,
                        "memory_HIGH",      0.55,
                        "errorRate_HIGH",   0.40))
                .build();
    }

    private static FaultHypothesis hypothesis(String svc, String category) {
        return FaultHypothesis.builder()
                .serviceId(svc)
                .localConfidence(0.74)
                .dominantFaultCategory(category)
                .firedRules(List.of("CPU_HIGH_LATENCY_HIGH"))
                .ruleFireStrengths(Map.of("CPU_HIGH_LATENCY_HIGH", 0.74))
                .build();
    }
}
