package com.foda.service.controller;

import com.foda.service.model.ServiceStatus;
import com.foda.service.service.MetricsCollectorService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;

/**
 * Status REST Controller
 * Exposes endpoints for retrieving service health status
 */
@RestController
@RequestMapping("/status")
@RequiredArgsConstructor
public class StatusController {

    private final MetricsCollectorService metricsCollectorService;

    @Value("${service.id}")
    private String serviceId;

    @Value("${service.version:1.0.0}")
    private String version;

    /**
     * Get service status
     * @return Service status information
     */
    @GetMapping
    public ResponseEntity<ServiceStatus> getStatus() {
        ServiceStatus status = ServiceStatus.builder()
                .serviceId(serviceId)
                .status("UP")
                .timestamp(Instant.now())
                .version(version)
                .uptimeSeconds(metricsCollectorService.getUptimeSeconds())
                .message("Service is running normally")
                .build();

        return ResponseEntity.ok(status);
    }

    /**
     * Health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}
