package com.foda.rca.inference;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;

/**
 * Fault Inference Layer interface (Section 3.2 of the FCP-RCA paper).
 *
 * <p>Given a fuzzified health vector {@link FuzzyVector}, the rule engine fires all
 * applicable {@link FuzzyRule} instances and aggregates their consequents into a
 * single local fault hypothesis {@link FaultHypothesis}.</p>
 *
 * <p>The canonical implementation is {@link MamdaniFuzzyRuleEngine}, which uses:</p>
 * <ul>
 *   <li><strong>Min-conjunction</strong> for antecedent aggregation.</li>
 *   <li><strong>Max-aggregation</strong> of fired rule strengths per fault category.</li>
 *   <li><strong>Max-defuzzification</strong> to select the dominant category.</li>
 * </ul>
 */
public interface FuzzyRuleEngine {

    /**
     * Apply the rule base to the given fuzzy vector and produce a local hypothesis.
     *
     * @param fuzzyVector fuzzified health state of the service
     * @return local fault hypothesis with confidence H ∈ [0, 1] and fired-rule evidence
     */
    FaultHypothesis infer(FuzzyVector fuzzyVector);
}
