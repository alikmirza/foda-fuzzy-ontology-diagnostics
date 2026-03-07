package com.foda.rca.model;

import lombok.Builder;
import lombok.Value;

/**
 * Raw telemetry observation for a single microservice at one point in time.
 *
 * <p>This is the <em>crisp input</em> to the fuzzification layer (Section 3.1 of the paper).
 * All metric values are in their natural units; the fuzzifier normalises them into [0,1]
 * membership degrees before inference begins.</p>
 *
 * <ul>
 *   <li>{@code cpuUsage}     – CPU utilisation in percent [0, 100]</li>
 *   <li>{@code latencyMs}    – P99 request latency in milliseconds</li>
 *   <li>{@code memoryUsage}  – JVM / OS heap utilisation in percent [0, 100]</li>
 *   <li>{@code errorRate}    – fraction of failed requests in [0, 1]</li>
 *   <li>{@code throughput}   – requests per second</li>
 * </ul>
 */
@Value
@Builder
public class ServiceMetrics {

    /** Unique identifier of the observed microservice. */
    String serviceId;

    /** CPU utilisation in percent [0, 100]. */
    double cpuUsage;

    /** P99 end-to-end request latency in milliseconds. */
    double latencyMs;

    /** Memory (heap) utilisation in percent [0, 100]. */
    double memoryUsage;

    /** Fraction of HTTP responses with 5xx status in [0, 1]. */
    double errorRate;

    /** Successful requests per second. */
    double throughput;

    /** ISO-8601 timestamp of the observation window. */
    String timestamp;
}
