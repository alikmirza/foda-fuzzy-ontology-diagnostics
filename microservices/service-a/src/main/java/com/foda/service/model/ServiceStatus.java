package com.foda.service.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Service Status Data Transfer Object
 * Represents the health and status of a microservice
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ServiceStatus {

    @JsonProperty("serviceId")
    private String serviceId;

    @JsonProperty("status")
    private String status; // UP, DOWN, DEGRADED

    @JsonProperty("timestamp")
    private Instant timestamp;

    @JsonProperty("version")
    private String version;

    @JsonProperty("uptime")
    private Long uptimeSeconds;

    @JsonProperty("message")
    private String message;
}
