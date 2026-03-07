package com.foda.fuzzy.service;

import com.foda.fuzzy.model.DiagnosticResult;
import com.foda.fuzzy.model.MLPrediction;

/**
 * Interface for Fuzzy Inference Service
 */
public interface FuzzyInferenceService {

    /**
     * Diagnose anomalies using fuzzy logic rules
     *
     * @param prediction ML prediction from anomaly detector
     * @return Diagnostic result with fault classification
     */
    DiagnosticResult diagnose(MLPrediction prediction);
}
