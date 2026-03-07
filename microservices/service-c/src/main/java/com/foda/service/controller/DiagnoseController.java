package com.foda.service.controller;

import com.foda.service.kafka.MetricsProducer;
import com.foda.service.model.ServiceMetrics;
import com.foda.service.service.MetricsCollectorService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Diagnose REST Controller
 * Provides endpoints for triggering diagnostic operations
 */
@RestController
@RequestMapping("/diagnose")
@RequiredArgsConstructor
@Slf4j
public class DiagnoseController {

    private final MetricsCollectorService metricsCollectorService;
    private final MetricsProducer metricsProducer;

    /**
     * Trigger immediate metrics collection and publication
     * @return Collected metrics
     */
    @PostMapping("/collect")
    public ResponseEntity<ServiceMetrics> triggerCollection() {
        ServiceMetrics metrics = metricsCollectorService.collectMetrics();
        metricsProducer.sendMetrics(metrics);
        log.info("Manually triggered metrics collection for {}", metrics.getServiceId());
        return ResponseEntity.ok(metrics);
    }

    /**
     * Get diagnostic summary
     * @return Diagnostic information
     */
    @GetMapping("/summary")
    public ResponseEntity<Map<String, Object>> getDiagnosticSummary() {
        ServiceMetrics metrics = metricsCollectorService.collectMetrics();

        Map<String, Object> summary = Map.of(
                "serviceId", metrics.getServiceId(),
                "timestamp", metrics.getTimestamp(),
                "uptimeSeconds", metricsCollectorService.getUptimeSeconds(),
                "currentMetrics", metrics,
                "healthStatus", evaluateHealth(metrics)
        );

        return ResponseEntity.ok(summary);
    }

    private String evaluateHealth(ServiceMetrics metrics) {
        if (metrics.getCpuUtilization() > 0.9 || metrics.getMemoryUtilization() > 0.9) {
            return "CRITICAL";
        } else if (metrics.getCpuUtilization() > 0.75 || metrics.getMemoryUtilization() > 0.75) {
            return "WARNING";
        } else if (metrics.getErrorRate() > 0.05) {
            return "WARNING";
        } else {
            return "HEALTHY";
        }
    }
}
