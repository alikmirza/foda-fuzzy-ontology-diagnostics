package com.foda.service;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Service A - Monitored Microservice
 *
 * This is one of the monitored microservices in the FODA architecture.
 * It publishes performance metrics (CPU, latency, throughput, etc.) to Kafka
 * for anomaly detection and diagnostic reasoning.
 */
@SpringBootApplication
@EnableScheduling
public class ServiceAApplication {

    public static void main(String[] args) {
        SpringApplication.run(ServiceAApplication.class, args);
    }
}
