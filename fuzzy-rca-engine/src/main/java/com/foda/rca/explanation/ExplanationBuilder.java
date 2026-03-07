package com.foda.rca.explanation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.RankedCause;

/**
 * Explanation Layer interface (Section 3.5 of the FCP-RCA paper).
 *
 * <p>Converts the algorithmic evidence (fuzzy memberships, fired rules, propagation path)
 * into a human-readable natural-language explanation that operators and auditors can act on.
 * The explanations are also suitable for inclusion in academic evaluation tables (Section 5).</p>
 */
public interface ExplanationBuilder {

    /**
     * Generate a natural-language explanation for a ranked root-cause candidate.
     *
     * @param cause     the ranked cause to explain
     * @param vector    fuzzified health state of the suspect service
     * @param hypothesis local fault hypothesis (fired rules and their strengths)
     * @return a multi-sentence NL explanation string
     */
    String explain(RankedCause cause, FuzzyVector vector, FaultHypothesis hypothesis);
}
