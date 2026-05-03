package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Worked example for AICT2026 paper §V: 3-node cyclic graph A→B→C→A,
 * uniform edge weights 0.7, δ=0.85, ε=1e-6.
 * Re-implements the same formula as IterativeConfidencePropagator so we can
 * print Δ_k at each iteration; then calls the production propagator to
 * confirm both reach the same fixed point.
 */
class WorkedExampleTest {

    @Test
    void workedExample_3nodeCycle_logResiduals() {
        // ----- Graph: A -> B -> C -> A, w = 0.7 on every edge -----
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.7)
                .addEdge("B", "C", 0.7)
                .addEdge("C", "A", 0.7)
                .build();

        // ----- Local symptom strengths H -----
        Map<String, Double> H = new LinkedHashMap<>();
        H.put("A", 0.6);
        H.put("B", 0.3);
        H.put("C", 0.2);

        Map<String, FaultHypothesis> hyps = new LinkedHashMap<>();
        for (Map.Entry<String, Double> e : H.entrySet()) {
            hyps.put(e.getKey(), FaultHypothesis.builder()
                    .serviceId(e.getKey())
                    .localConfidence(e.getValue())
                    .dominantFaultCategory("TEST")
                    .firedRules(List.of())
                    .ruleFireStrengths(Map.of())
                    .build());
        }

        // ----- Parameters -----
        final double delta_d = 0.85;          // damping factor δ
        final double epsilon = 1e-6;          // convergence threshold ε
        final int    MAX_ITER = 100;

        // ----- Manual Jacobi iteration (mirrors IterativeConfidencePropagator) -----
        Map<String, Double> C = new LinkedHashMap<>(H);   // C^0 = H
        System.out.println("=== Worked Example: 3-node cyclic graph A->B->C->A ===");
        System.out.println("H(A)=" + H.get("A") + ", H(B)=" + H.get("B") + ", H(C)=" + H.get("C"));
        System.out.println("delta=" + delta_d + ", epsilon=" + epsilon);
        System.out.printf("C^0 : A=%.10f  B=%.10f  C=%.10f%n",
                C.get("A"), C.get("B"), C.get("C"));

        int iter = 0;
        double residual = Double.MAX_VALUE;
        while (residual > epsilon && iter < MAX_ITER) {
            Map<String, Double> Cprev = new LinkedHashMap<>(C);

            for (String s : g.getServices()) {
                List<Edge> callees = g.getOutgoingEdges(s);
                double complementProduct = 1.0;
                for (Edge e : callees) {
                    double ct         = Cprev.getOrDefault(e.getTarget(), 0.0);
                    double effectiveW = e.getWeight() * delta_d;
                    complementProduct *= (1.0 - ct * effectiveW);
                }
                double p  = 1.0 - complementProduct;
                double hs = H.get(s);
                double cs = 1.0 - (1.0 - hs) * (1.0 - p);
                if (cs < 0.0) cs = 0.0;
                if (cs > 1.0) cs = 1.0;
                C.put(s, cs);
            }

            residual = 0.0;
            for (String s : g.getServices()) {
                residual = Math.max(residual, Math.abs(C.get(s) - Cprev.get(s)));
            }
            iter++;
            System.out.printf("k=%2d  C(A)=%.10f  C(B)=%.10f  C(C)=%.10f   Delta=%.3e%n",
                    iter, C.get("A"), C.get("B"), C.get("C"), residual);
        }

        System.out.println("--- Converged ---");
        System.out.println("Iterations to convergence: " + iter);
        System.out.printf("Final C(A) = %.10f%n", C.get("A"));
        System.out.printf("Final C(B) = %.10f%n", C.get("B"));
        System.out.printf("Final C(C) = %.10f%n", C.get("C"));

        // ----- Cross-check against production IterativeConfidencePropagator -----
        IterativeConfidencePropagator prod =
                new IterativeConfidencePropagator(delta_d, epsilon, MAX_ITER);
        Map<String, Double> prodC = prod.propagate(hyps, g);
        System.out.println("--- Production propagator check ---");
        System.out.printf("Prod C(A) = %.10f%n", prodC.get("A"));
        System.out.printf("Prod C(B) = %.10f%n", prodC.get("B"));
        System.out.printf("Prod C(C) = %.10f%n", prodC.get("C"));

        assertEquals(C.get("A"), prodC.get("A"), 1e-9, "C(A) mismatch with production propagator");
        assertEquals(C.get("B"), prodC.get("B"), 1e-9, "C(B) mismatch with production propagator");
        assertEquals(C.get("C"), prodC.get("C"), 1e-9, "C(C) mismatch with production propagator");
    }
}
