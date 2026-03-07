package com.foda.service.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Service Metrics Data Transfer Object
 * Represents the performance metrics of a microservice
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ServiceMetrics {

    @JsonProperty("serviceId")
    private String serviceId;

    @JsonProperty("timestamp")
    private Instant timestamp;

    @JsonProperty("cpuUtilization")
    private Double cpuUtilization;

    @JsonProperty("memoryUtilization")
    private Double memoryUtilization;

    @JsonProperty("latencyMs")
    private Double latencyMs;

    @JsonProperty("throughput")
    private Double throughput;

    @JsonProperty("errorRate")
    private Double errorRate;

    @JsonProperty("diskIo")
    private Double diskIo;

    @JsonProperty("networkIn")
    private Double networkIn;

    @JsonProperty("networkOut")
    private Double networkOut;

    @JsonProperty("connectionCount")
    private Integer connectionCount;

    @JsonProperty("requestCount")
    private Long requestCount;

    @JsonProperty("responseTimeP50")
    private Double responseTimeP50;

    @JsonProperty("responseTimeP95")
    private Double responseTimeP95;

    @JsonProperty("responseTimeP99")
    private Double responseTimeP99;
}
