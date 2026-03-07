package com.foda.fuzzy.controller;

import com.foda.fuzzy.model.DiagnosticResult;
import com.foda.fuzzy.model.MLPrediction;
import com.foda.fuzzy.service.FuzzyInferenceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/fuzzy")
@RequiredArgsConstructor
@Slf4j
public class FuzzyDiagnosticController {

    private final FuzzyInferenceService fuzzyInferenceService;

    @PostMapping("/diagnose")
    public ResponseEntity<DiagnosticResult> diagnose(@RequestBody MLPrediction prediction) {
        log.info("Manual diagnosis request for service: {}", prediction.getServiceId());

        try {
            DiagnosticResult result = fuzzyInferenceService.diagnose(prediction);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("Error during manual diagnosis", e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/health")
    public ResponseEntity<HealthResponse> health() {
        return ResponseEntity.ok(HealthResponse.builder()
                .status("UP")
                .service("fuzzy-engine")
                .timestamp(java.time.Instant.now().toString())
                .build());
    }

    @lombok.Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    public static class HealthResponse {
        private String status;
        private String service;
        private String timestamp;
    }
}
