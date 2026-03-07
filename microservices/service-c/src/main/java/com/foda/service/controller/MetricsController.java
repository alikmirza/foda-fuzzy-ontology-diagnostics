package com.foda.service.controller;

import com.foda.service.model.ServiceMetrics;
import com.foda.service.service.MetricsCollectorService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Metrics REST Controller
 * Exposes endpoints for retrieving current service metrics
 */
@RestController
@RequestMapping("/metrics")
@RequiredArgsConstructor
public class MetricsController {

    private final MetricsCollectorService metricsCollectorService;

    /**
     * Get current service metrics
     * @return Current service metrics
     */
    @GetMapping
    public ResponseEntity<ServiceMetrics> getMetrics() {
        ServiceMetrics metrics = metricsCollectorService.collectMetrics();
        return ResponseEntity.ok(metrics);
    }
}
