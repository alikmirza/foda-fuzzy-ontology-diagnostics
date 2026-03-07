package com.foda.ontology.controller;

import com.foda.ontology.service.FusekiService;
import com.foda.ontology.service.SparqlQueryService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/ontology")
@RequiredArgsConstructor
@Slf4j
public class QueryController {

    private final SparqlQueryService sparqlQueryService;
    private final FusekiService fusekiService;

    @GetMapping("/diagnostics/service/{serviceId}")
    public ResponseEntity<List<Map<String, String>>> getDiagnosticsByService(@PathVariable String serviceId) {
        log.info("Query: diagnostics for service {}", serviceId);
        List<Map<String, String>> results = sparqlQueryService.getDiagnosticsByService(serviceId);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/diagnostics/fault/{faultType}")
    public ResponseEntity<List<Map<String, String>>> getDiagnosticsByFaultType(@PathVariable String faultType) {
        log.info("Query: diagnostics for fault type {}", faultType);
        List<Map<String, String>> results = sparqlQueryService.getDiagnosticsByFaultType(faultType);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/diagnostics/severity/{severity}")
    public ResponseEntity<List<Map<String, String>>> getDiagnosticsBySeverity(@PathVariable String severity) {
        log.info("Query: diagnostics for severity {}", severity);
        List<Map<String, String>> results = sparqlQueryService.getDiagnosticsBySeverity(severity);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/diagnostics/{diagnosticId}")
    public ResponseEntity<Map<String, String>> getDiagnosticDetails(@PathVariable String diagnosticId) {
        log.info("Query: details for diagnostic {}", diagnosticId);
        Map<String, String> result = sparqlQueryService.getDiagnosticDetails(diagnosticId);
        if (result == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(result);
    }

    @GetMapping("/diagnostics/{diagnosticId}/recommendations")
    public ResponseEntity<List<Map<String, String>>> getRecommendations(@PathVariable String diagnosticId) {
        log.info("Query: recommendations for diagnostic {}", diagnosticId);
        List<Map<String, String>> results = sparqlQueryService.getRecommendations(diagnosticId);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/diagnostics/{diagnosticId}/factors")
    public ResponseEntity<List<Map<String, String>>> getContributingFactors(@PathVariable String diagnosticId) {
        log.info("Query: contributing factors for diagnostic {}", diagnosticId);
        List<Map<String, String>> results = sparqlQueryService.getContributingFactors(diagnosticId);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/diagnostics/recent")
    public ResponseEntity<List<Map<String, String>>> getRecentDiagnostics(
            @RequestParam(defaultValue = "10") int limit) {
        log.info("Query: recent diagnostics (limit={})", limit);
        List<Map<String, String>> results = sparqlQueryService.getRecentDiagnostics(limit);
        return ResponseEntity.ok(results);
    }

    @GetMapping("/statistics/faults")
    public ResponseEntity<List<Map<String, String>>> getFaultStatistics() {
        log.info("Query: fault statistics");
        List<Map<String, String>> results = sparqlQueryService.getFaultStatistics();
        return ResponseEntity.ok(results);
    }

    @PostMapping("/query/sparql")
    public ResponseEntity<List<Map<String, String>>> executeSparqlQuery(@RequestBody String sparqlQuery) {
        log.info("Executing custom SPARQL query");
        try {
            List<Map<String, String>> results = fusekiService.executeQuery(sparqlQuery);
            return ResponseEntity.ok(results);
        } catch (Exception e) {
            log.error("Error executing SPARQL query", e);
            return ResponseEntity.badRequest().build();
        }
    }

    @GetMapping("/health")
    public ResponseEntity<HealthResponse> health() {
        boolean fusekiAvailable = fusekiService.isAvailable();
        long tripleCount = fusekiAvailable ? fusekiService.getTripleCount() : 0;

        return ResponseEntity.ok(HealthResponse.builder()
                .status(fusekiAvailable ? "UP" : "DOWN")
                .service("ontology-mapper")
                .fusekiAvailable(fusekiAvailable)
                .tripleCount(tripleCount)
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
        private Boolean fusekiAvailable;
        private Long tripleCount;
        private String timestamp;
    }
}
