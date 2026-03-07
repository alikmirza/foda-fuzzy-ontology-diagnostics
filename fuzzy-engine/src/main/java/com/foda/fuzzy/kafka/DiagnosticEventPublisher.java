package com.foda.fuzzy.kafka;

import com.foda.fuzzy.model.DiagnosticResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

import java.util.concurrent.CompletableFuture;

@Component
@Slf4j
@RequiredArgsConstructor
public class DiagnosticEventPublisher {

    private final KafkaTemplate<String, DiagnosticResult> kafkaTemplate;

    @Value("${kafka.topic.diagnostic-events}")
    private String diagnosticEventsTopic;

    public void publishDiagnostic(DiagnosticResult diagnosticResult) {
        try {
            String key = diagnosticResult.getServiceId();

            CompletableFuture<SendResult<String, DiagnosticResult>> future =
                    kafkaTemplate.send(diagnosticEventsTopic, key, diagnosticResult);

            future.whenComplete((result, ex) -> {
                if (ex == null) {
                    log.info("Published diagnostic event: topic={}, partition={}, offset={}, diagnosticId={}",
                            result.getRecordMetadata().topic(),
                            result.getRecordMetadata().partition(),
                            result.getRecordMetadata().offset(),
                            diagnosticResult.getDiagnosticId());
                } else {
                    log.error("Failed to publish diagnostic event: diagnosticId={}",
                            diagnosticResult.getDiagnosticId(), ex);
                }
            });

        } catch (Exception e) {
            log.error("Error publishing diagnostic event: diagnosticId={}",
                    diagnosticResult.getDiagnosticId(), e);
        }
    }
}
