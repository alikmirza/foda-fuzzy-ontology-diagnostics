package com.foda.service.service;

import com.foda.service.kafka.MetricsProducer;
import com.foda.service.model.ServiceMetrics;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.OperatingSystemMXBean;
import java.time.Instant;
import java.util.Random;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Metrics Collector Service
 * Collects system and application metrics and publishes them to Kafka
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class MetricsCollectorService {

    private final MetricsProducer metricsProducer;
    private final Random random = new Random();
    private final AtomicLong requestCounter = new AtomicLong(0);

    @Value("${service.id}")
    private String serviceId;

    @Value("${metrics.collection.enabled:true}")
    private boolean metricsEnabled;

    @Value("${metrics.anomaly.simulation:false}")
    private boolean simulateAnomaly;

    private final Instant startTime = Instant.now();

    /**
     * Collect and publish metrics every 10 seconds
     */
    @Scheduled(fixedRateString = "${metrics.collection.interval:10000}")
    public void collectAndPublishMetrics() {
        if (!metricsEnabled) {
            return;
        }

        try {
            ServiceMetrics metrics = collectMetrics();
            metricsProducer.sendMetrics(metrics);
            log.debug("Published metrics for {}: CPU={}, Memory={}, Latency={}ms",
                    serviceId, metrics.getCpuUtilization(), metrics.getMemoryUtilization(), metrics.getLatencyMs());
        } catch (Exception e) {
            log.error("Error collecting/publishing metrics", e);
        }
    }

    /**
     * Collect current system metrics
     */
    public ServiceMetrics collectMetrics() {
        OperatingSystemMXBean osBean = ManagementFactory.getOperatingSystemMXBean();
        MemoryMXBean memoryBean = ManagementFactory.getMemoryMXBean();

        double cpuUtilization = getCpuUtilization(osBean);
        double memoryUtilization = getMemoryUtilization(memoryBean);

        // Simulate anomalies if enabled
        if (simulateAnomaly && random.nextDouble() < 0.1) { // 10% chance of anomaly
            cpuUtilization = Math.min(0.85 + random.nextDouble() * 0.15, 1.0); // 85-100%
            memoryUtilization = Math.min(0.80 + random.nextDouble() * 0.20, 1.0); // 80-100%
        }

        return ServiceMetrics.builder()
                .serviceId(serviceId)
                .timestamp(Instant.now())
                .cpuUtilization(cpuUtilization)
                .memoryUtilization(memoryUtilization)
                .latencyMs(calculateLatency())
                .throughput(calculateThroughput())
                .errorRate(calculateErrorRate())
                .diskIo(random.nextDouble() * 100) // Simulated
                .networkIn(random.nextDouble() * 1000) // Simulated MB/s
                .networkOut(random.nextDouble() * 500) // Simulated MB/s
                .connectionCount(random.nextInt(100) + 10)
                .requestCount(requestCounter.incrementAndGet())
                .responseTimeP50(50 + random.nextDouble() * 50)
                .responseTimeP95(150 + random.nextDouble() * 100)
                .responseTimeP99(300 + random.nextDouble() * 200)
                .build();
    }

    private double getCpuUtilization(OperatingSystemMXBean osBean) {
        double systemLoad = osBean.getSystemLoadAverage();
        int availableProcessors = osBean.getAvailableProcessors();

        // Normalize system load
        if (systemLoad >= 0) {
            return Math.min(systemLoad / availableProcessors, 1.0);
        }

        // Fallback to simulated value if system load not available
        return 0.3 + random.nextDouble() * 0.4; // 30-70% normal load
    }

    private double getMemoryUtilization(MemoryMXBean memoryBean) {
        long used = memoryBean.getHeapMemoryUsage().getUsed();
        long max = memoryBean.getHeapMemoryUsage().getMax();

        if (max > 0) {
            return (double) used / max;
        }

        // Fallback to simulated value
        return 0.4 + random.nextDouble() * 0.3; // 40-70% normal memory
    }

    private double calculateLatency() {
        // Simulate normal latency with occasional spikes
        double baseLatency = 50 + random.nextDouble() * 100; // 50-150ms

        if (simulateAnomaly && random.nextDouble() < 0.05) { // 5% chance of spike
            baseLatency += 200 + random.nextDouble() * 300; // Add 200-500ms
        }

        return baseLatency;
    }

    private double calculateThroughput() {
        // Simulate throughput (requests per second)
        double baseThroughput = 400 + random.nextDouble() * 300; // 400-700 req/s

        if (simulateAnomaly && random.nextDouble() < 0.05) {
            baseThroughput *= 0.3; // Drop to 30% during anomaly
        }

        return baseThroughput;
    }

    private double calculateErrorRate() {
        // Normal error rate: 0-1%
        double errorRate = random.nextDouble() * 0.01;

        if (simulateAnomaly && random.nextDouble() < 0.05) {
            errorRate = 0.02 + random.nextDouble() * 0.03; // 2-5% error rate
        }

        return errorRate;
    }

    public long getUptimeSeconds() {
        return Instant.now().getEpochSecond() - startTime.getEpochSecond();
    }
}
