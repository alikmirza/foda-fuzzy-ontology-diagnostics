package com.foda.explanation.controller;

import com.foda.explanation.model.DiagnosticResult;
import com.foda.explanation.model.ExplanationResult;
import com.foda.explanation.repository.ExplanationRepository;
import com.foda.explanation.service.ExplanationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * REST API for retrieving and generating explanations.
 */
@RestController
@RequestMapping("/explanation")
@Slf4j
@RequiredArgsConstructor
public class ExplanationController {

    private final ExplanationService explanationService;
    private final ExplanationRepository explanationRepository;

    /**
     * Health check endpoint.
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "explanation-service",
                "version", "1.0.0"
        ));
    }

    /**
     * Generate explanation for a diagnostic result on-demand (for testing/manual triggers).
     */
    @PostMapping("/generate")
    public ResponseEntity<ExplanationResult> generateExplanation(@RequestBody DiagnosticResult diagnostic) {
        log.info("Manual explanation request for service: {}", diagnostic.getServiceId());
        ExplanationResult result = explanationService.generateExplanation(diagnostic);
        explanationRepository.save(result);
        return ResponseEntity.ok(result);
    }

    /**
     * Get recent explanations (default last 10).
     */
    @GetMapping("/recent")
    public ResponseEntity<List<Map<String, Object>>> getRecentExplanations(
            @RequestParam(defaultValue = "10") int limit) {
        List<Map<String, Object>> results = explanationRepository.findRecent(limit);
        return ResponseEntity.ok(results);
    }

    /**
     * Get explanations for a specific service.
     */
    @GetMapping("/service/{serviceId}")
    public ResponseEntity<List<Map<String, Object>>> getByService(
            @PathVariable String serviceId,
            @RequestParam(defaultValue = "20") int limit) {
        List<Map<String, Object>> results = explanationRepository.findByServiceId(serviceId, limit);
        return ResponseEntity.ok(results);
    }

    /**
     * Get explanations by fault type.
     */
    @GetMapping("/fault/{faultType}")
    public ResponseEntity<List<Map<String, Object>>> getByFaultType(
            @PathVariable String faultType,
            @RequestParam(defaultValue = "20") int limit) {
        List<Map<String, Object>> results = explanationRepository.findByFaultType(faultType, limit);
        return ResponseEntity.ok(results);
    }

    /**
     * Get a specific explanation by ID.
     */
    @GetMapping("/{explanationId}")
    public ResponseEntity<Map<String, Object>> getById(@PathVariable String explanationId) {
        Optional<Map<String, Object>> result = explanationRepository.findById(explanationId);
        return result.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Get fault statistics from stored explanations.
     */
    @GetMapping("/statistics")
    public ResponseEntity<Map<String, Object>> getStatistics() {
        Map<String, Object> stats = explanationRepository.getFaultStatistics();
        return ResponseEntity.ok(stats);
    }
}
