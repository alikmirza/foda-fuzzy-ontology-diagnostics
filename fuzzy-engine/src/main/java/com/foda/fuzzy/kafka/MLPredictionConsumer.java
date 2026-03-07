package com.foda.fuzzy.kafka;

import com.foda.fuzzy.model.DiagnosticResult;
import com.foda.fuzzy.model.MLPrediction;
import com.foda.fuzzy.service.FuzzyInferenceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@Slf4j
@RequiredArgsConstructor
public class MLPredictionConsumer {

    private final FuzzyInferenceService fuzzyInferenceService;
    private final DiagnosticEventPublisher diagnosticEventPublisher;

    @KafkaListener(
            topics = "${kafka.topic.ml-predictions}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "mlPredictionKafkaListenerContainerFactory"
    )
    public void consumeMLPrediction(MLPrediction prediction) {
        try {
            log.info("Received ML prediction for service: {}, predictionId: {}, isAnomaly: {}",
                    prediction.getServiceId(),
                    prediction.getPredictionId(),
                    prediction.getIsAnomaly());

            // Only process anomalies
            if (Boolean.TRUE.equals(prediction.getIsAnomaly())) {
                // Perform fuzzy inference
                DiagnosticResult diagnosticResult = fuzzyInferenceService.diagnose(prediction);

                log.info("Fuzzy diagnosis completed: service={}, fault={}, severity={}, FCI={}",
                        diagnosticResult.getServiceId(),
                        diagnosticResult.getFaultType(),
                        diagnosticResult.getSeverity(),
                        diagnosticResult.getFci());

                // Publish diagnostic result
                diagnosticEventPublisher.publishDiagnostic(diagnosticResult);
            } else {
                log.debug("Skipping normal prediction (no anomaly): predictionId={}",
                        prediction.getPredictionId());
            }

        } catch (Exception e) {
            log.error("Error processing ML prediction: predictionId={}",
                    prediction.getPredictionId(), e);
        }
    }
}
