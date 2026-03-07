package com.foda.service.kafka;

import com.foda.service.model.ServiceMetrics;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

import java.util.concurrent.CompletableFuture;

/**
 * Kafka Producer for Service Metrics
 * Publishes metrics to the metrics-stream topic
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class MetricsProducer {

    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${kafka.topic.metrics:metrics-stream}")
    private String metricsTopic;

    /**
     * Send service metrics to Kafka
     * @param metrics The service metrics to publish
     */
    public void sendMetrics(ServiceMetrics metrics) {
        try {
            CompletableFuture<SendResult<String, Object>> future =
                    kafkaTemplate.send(metricsTopic, metrics.getServiceId(), metrics);

            future.whenComplete((result, ex) -> {
                if (ex == null) {
                    log.trace("Sent metrics for service {}: offset={}",
                            metrics.getServiceId(),
                            result.getRecordMetadata().offset());
                } else {
                    log.error("Failed to send metrics for service {}: {}",
                            metrics.getServiceId(), ex.getMessage());
                }
            });
        } catch (Exception e) {
            log.error("Error sending metrics to Kafka", e);
        }
    }
}
