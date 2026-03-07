package com.foda.rca.fuzzification;

import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.ServiceMetrics;

/**
 * Fuzzification Layer interface (Section 3.1 of the FCP-RCA paper).
 *
 * <p>Transforms a crisp {@link ServiceMetrics} observation into a {@link FuzzyVector}
 * containing membership degrees for every linguistic variable used by the rule engine.
 * The linguistic universe covers four metric dimensions:</p>
 *
 * <table border="1">
 *   <tr><th>Metric</th><th>Linguistic terms</th></tr>
 *   <tr><td>CPU usage (%)</td><td>LOW, MEDIUM, HIGH</td></tr>
 *   <tr><td>Latency (ms)</td><td>NORMAL, ELEVATED, CRITICAL</td></tr>
 *   <tr><td>Memory usage (%)</td><td>LOW, MEDIUM, HIGH</td></tr>
 *   <tr><td>Error rate (0–1)</td><td>NONE, LOW, ELEVATED, HIGH</td></tr>
 * </table>
 *
 * <p>A throughput dimension is also encoded as LOW/NORMAL to capture degradation.</p>
 */
public interface FaultFuzzifier {

    /**
     * Fuzzify the raw service metric observation.
     *
     * @param metrics non-null crisp metric observation
     * @return a {@link FuzzyVector} with membership degrees for all linguistic labels
     */
    FuzzyVector fuzzify(ServiceMetrics metrics);
}
