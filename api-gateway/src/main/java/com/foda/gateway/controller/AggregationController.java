package com.foda.gateway.controller;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/dashboard")
@Slf4j
public class AggregationController {

    private final WebClient webClient;

    @Value("${SERVICE_A_URL:http://localhost:8081}")
    private String serviceAUrl;

    @Value("${SERVICE_B_URL:http://localhost:8082}")
    private String serviceBUrl;

    @Value("${SERVICE_C_URL:http://localhost:8083}")
    private String serviceCUrl;

    @Value("${ML_SERVICE_URL:http://localhost:8000}")
    private String mlServiceUrl;

    @Value("${FUZZY_ENGINE_URL:http://localhost:8084}")
    private String fuzzyEngineUrl;

    @Value("${ONTOLOGY_MAPPER_URL:http://localhost:8085}")
    private String ontologyMapperUrl;

    @Value("${EXPLANATION_SERVICE_URL:http://localhost:8086}")
    private String explanationServiceUrl;

    public AggregationController(WebClient.Builder webClientBuilder) {
        this.webClient = webClientBuilder.build();
    }

    @GetMapping("/health")
    public Mono<ResponseEntity<Map<String, Object>>> getSystemHealth() {
        log.info("Fetching system health status");

        return Mono.zip(
                getServiceHealth(serviceAUrl, "service-a"),
                getServiceHealth(serviceBUrl, "service-b"),
                getServiceHealth(serviceCUrl, "service-c"),
                getServiceHealth(mlServiceUrl, "ml-service"),
                getServiceHealth(fuzzyEngineUrl, "fuzzy-engine"),
                Mono.zip(
                        getServiceHealth(ontologyMapperUrl, "ontology-mapper"),
                        getServiceHealth(explanationServiceUrl, "explanation-service")
                )
        ).map(tuple -> {
            Map<String, Object> health = new HashMap<>();
            health.put("service-a", tuple.getT1());
            health.put("service-b", tuple.getT2());
            health.put("service-c", tuple.getT3());
            health.put("ml-service", tuple.getT4());
            health.put("fuzzy-engine", tuple.getT5());
            health.put("ontology-mapper", tuple.getT6().getT1());
            health.put("explanation-service", tuple.getT6().getT2());
            health.put("timestamp", java.time.Instant.now().toString());

            // Calculate overall status
            boolean allHealthy = health.values().stream()
                    .filter(v -> v instanceof Map)
                    .map(v -> (Map<?, ?>) v)
                    .allMatch(m -> "UP".equals(m.get("status")));

            health.put("overallStatus", allHealthy ? "UP" : "DEGRADED");

            return ResponseEntity.ok(health);
        }).onErrorResume(e -> {
            log.error("Error fetching system health", e);
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("overallStatus", "DOWN");
            errorResponse.put("error", e.getMessage());
            return Mono.just(ResponseEntity.status(503).body(errorResponse));
        });
    }

    @GetMapping("/overview")
    public Mono<ResponseEntity<Map<String, Object>>> getSystemOverview() {
        log.info("Fetching system overview");

        return Mono.zip(
                getRecentDiagnostics(),
                getFaultStatistics(),
                getSystemHealth()
        ).map(tuple -> {
            Map<String, Object> overview = new HashMap<>();
            overview.put("recentDiagnostics", tuple.getT1().getBody());
            overview.put("faultStatistics", tuple.getT2().getBody());
            overview.put("systemHealth", tuple.getT3().getBody());
            overview.put("timestamp", java.time.Instant.now().toString());

            return ResponseEntity.ok(overview);
        }).onErrorResume(e -> {
            log.error("Error fetching system overview", e);
            return Mono.just(ResponseEntity.status(500).build());
        });
    }

    private Mono<Map<String, Object>> getServiceHealth(String baseUrl, String serviceName) {
        String healthEndpoint;
        if (serviceName.startsWith("service-")) {
            healthEndpoint = baseUrl + "/status";
        } else if (serviceName.equals("ml-service")) {
            healthEndpoint = baseUrl + "/health";
        } else if (serviceName.equals("fuzzy-engine")) {
            healthEndpoint = baseUrl + "/fuzzy/health";
        } else if (serviceName.equals("explanation-service")) {
            healthEndpoint = baseUrl + "/explanation/health";
        } else {
            healthEndpoint = baseUrl + "/ontology/health";
        }

        return webClient.get()
                .uri(healthEndpoint)
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> {
                    Map<String, Object> health = new HashMap<>();
                    health.put("status", "UP");
                    health.put("details", response);
                    return health;
                })
                .onErrorResume(e -> {
                    log.warn("Service {} is down: {}", serviceName, e.getMessage());
                    Map<String, Object> health = new HashMap<>();
                    health.put("status", "DOWN");
                    health.put("error", e.getMessage());
                    return Mono.just(health);
                });
    }

    private Mono<ResponseEntity<Object>> getRecentDiagnostics() {
        return webClient.get()
                .uri(ontologyMapperUrl + "/ontology/diagnostics/recent?limit=10")
                .retrieve()
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorReturn(ResponseEntity.status(503).build());
    }

    private Mono<ResponseEntity<Object>> getFaultStatistics() {
        return webClient.get()
                .uri(ontologyMapperUrl + "/ontology/statistics/faults")
                .retrieve()
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorReturn(ResponseEntity.status(503).build());
    }
}
