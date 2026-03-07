package com.foda.explanation.kafka;

import com.foda.explanation.model.DiagnosticResult;
import com.foda.explanation.model.ExplanationResult;
import com.foda.explanation.repository.ExplanationRepository;
import com.foda.explanation.service.ExplanationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

/**
 * Kafka consumer that listens to diagnostic-events and triggers explanation generation.
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class DiagnosticConsumer {

    private final ExplanationService explanationService;
    private final ExplanationRepository explanationRepository;

    @KafkaListener(
            topics = "${kafka.topic.diagnostic-events}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "diagnosticKafkaListenerContainerFactory"
    )
    public void consumeDiagnosticEvent(DiagnosticResult diagnostic) {
        try {
            log.info("Received diagnostic event: serviceId={}, fault={}, severity={}, fci={}",
                    diagnostic.getServiceId(),
                    diagnostic.getFaultType(),
                    diagnostic.getSeverity(),
                    diagnostic.getFci());

            // Generate explanation
            ExplanationResult explanation = explanationService.generateExplanation(diagnostic);

            // Persist to PostgreSQL
            explanationRepository.save(explanation);

            log.info("Explanation stored: explanationId={}, service={}, confidence={}",
                    explanation.getExplanationId(),
                    explanation.getServiceId(),
                    explanation.getCrispConfidence());

        } catch (Exception e) {
            log.error("Error processing diagnostic event for service: {}",
                    diagnostic.getServiceId(), e);
        }
    }
}
