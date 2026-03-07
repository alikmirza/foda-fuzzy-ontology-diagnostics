-- FODA Database Initialization Script
-- PostgreSQL database for storing metrics and historical data

-- Create schema
CREATE SCHEMA IF NOT EXISTS foda;

-- Service Metrics Table
CREATE TABLE IF NOT EXISTS foda.service_metrics (
    id BIGSERIAL PRIMARY KEY,
    service_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cpu_utilization DOUBLE PRECISION,
    memory_utilization DOUBLE PRECISION,
    latency_ms DOUBLE PRECISION,
    throughput DOUBLE PRECISION,
    error_rate DOUBLE PRECISION,
    disk_io DOUBLE PRECISION,
    network_in DOUBLE PRECISION,
    network_out DOUBLE PRECISION,
    connection_count INTEGER,
    request_count BIGINT,
    response_time_p50 DOUBLE PRECISION,
    response_time_p95 DOUBLE PRECISION,
    response_time_p99 DOUBLE PRECISION,
    CONSTRAINT chk_cpu CHECK (cpu_utilization >= 0 AND cpu_utilization <= 1),
    CONSTRAINT chk_memory CHECK (memory_utilization >= 0 AND memory_utilization <= 1),
    CONSTRAINT chk_error_rate CHECK (error_rate >= 0 AND error_rate <= 1)
);

-- Create index for efficient time-series queries
CREATE INDEX idx_service_metrics_service_time ON foda.service_metrics(service_id, timestamp DESC);

-- ML Predictions Table
CREATE TABLE IF NOT EXISTS foda.ml_predictions (
    id BIGSERIAL PRIMARY KEY,
    prediction_id UUID UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_id VARCHAR(100) NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    confidence DOUBLE PRECISION,
    model_used VARCHAR(100),
    feature_importance JSONB,
    ensemble_votes JSONB
    -- Foreign key removed: service_id is just a reference field, not enforced
    -- Services may generate predictions before being registered
);

CREATE INDEX idx_ml_predictions_service_time ON foda.ml_predictions(service_id, timestamp DESC);
CREATE INDEX idx_ml_predictions_anomaly ON foda.ml_predictions(is_anomaly, timestamp DESC);

-- Diagnostic Events Table
CREATE TABLE IF NOT EXISTS foda.diagnostic_events (
    id BIGSERIAL PRIMARY KEY,
    explanation_id UUID UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_id VARCHAR(100) NOT NULL,
    diagnostic_result VARCHAR(200) NOT NULL,
    fuzzy_confidence DOUBLE PRECISION,
    ml_anomaly_score DOUBLE PRECISION,
    ml_confidence DOUBLE PRECISION,
    crisp_confidence BOOLEAN,
    causal_chain JSONB,
    ontology_iri TEXT,
    suggested_actions JSONB,
    provenance JSONB
);

CREATE INDEX idx_diagnostic_events_service_time ON foda.diagnostic_events(service_id, timestamp DESC);
CREATE INDEX idx_diagnostic_events_result ON foda.diagnostic_events(diagnostic_result, timestamp DESC);

-- Anomaly Types Reference Table
CREATE TABLE IF NOT EXISTS foda.anomaly_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    severity VARCHAR(20),
    ontology_iri TEXT
);

-- Insert common anomaly types
INSERT INTO foda.anomaly_types (type_name, description, severity, ontology_iri) VALUES
    ('ResourceContention', 'High resource utilization causing performance degradation', 'HIGH', 'http://foda.org/DiagnosticKB#ResourceContention'),
    ('HighCPU', 'CPU utilization exceeding normal thresholds', 'MEDIUM', 'http://foda.org/DiagnosticKB#HighCPU'),
    ('MemoryLeak', 'Progressive memory consumption indicating possible leak', 'HIGH', 'http://foda.org/DiagnosticKB#MemoryLeak'),
    ('LatencySpike', 'Abnormal increase in response times', 'MEDIUM', 'http://foda.org/DiagnosticKB#LatencySpike'),
    ('NetworkPartition', 'Network connectivity issues between services', 'CRITICAL', 'http://foda.org/DiagnosticKB#NetworkPartition'),
    ('ErrorRateIncrease', 'Higher than normal error rates', 'HIGH', 'http://foda.org/DiagnosticKB#ErrorRateIncrease'),
    ('ThroughputDrop', 'Significant decrease in request throughput', 'MEDIUM', 'http://foda.org/DiagnosticKB#ThroughputDrop'),
    ('ModelDrift', 'ML model performance degradation', 'LOW', 'http://foda.org/DiagnosticKB#ModelDrift')
ON CONFLICT (type_name) DO NOTHING;

-- Service Registry Table
CREATE TABLE IF NOT EXISTS foda.service_registry (
    id SERIAL PRIMARY KEY,
    service_id VARCHAR(100) UNIQUE NOT NULL,
    service_name VARCHAR(200),
    service_type VARCHAR(50),
    version VARCHAR(50),
    host VARCHAR(255),
    port INTEGER,
    health_endpoint VARCHAR(255),
    metrics_endpoint VARCHAR(255),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP
);

-- Training Data Table for ML
CREATE TABLE IF NOT EXISTS foda.ml_training_data (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_id VARCHAR(100),
    features JSONB NOT NULL,
    label VARCHAR(50),
    is_anomaly BOOLEAN,
    used_for_training BOOLEAN DEFAULT FALSE,
    training_batch_id VARCHAR(100)
);

CREATE INDEX idx_ml_training_service ON foda.ml_training_data(service_id, timestamp DESC);
CREATE INDEX idx_ml_training_batch ON foda.ml_training_data(training_batch_id);

-- Audit Log Table
CREATE TABLE IF NOT EXISTS foda.audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(100) NOT NULL,
    component VARCHAR(100),
    service_id VARCHAR(100),
    user_id VARCHAR(100),
    action VARCHAR(200),
    details JSONB,
    success BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_audit_log_time ON foda.audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_component ON foda.audit_log(component, timestamp DESC);

-- Create views for common queries

-- Recent Anomalies View
CREATE OR REPLACE VIEW foda.recent_anomalies AS
SELECT
    de.explanation_id,
    de.timestamp,
    de.service_id,
    de.diagnostic_result,
    de.fuzzy_confidence,
    de.ml_confidence,
    at.severity,
    at.description
FROM foda.diagnostic_events de
LEFT JOIN foda.anomaly_types at ON de.diagnostic_result = at.type_name
WHERE de.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY de.timestamp DESC;

-- Service Health Summary View
CREATE OR REPLACE VIEW foda.service_health_summary AS
SELECT
    sr.service_id,
    sr.service_name,
    sr.status,
    COUNT(DISTINCT de.id) as anomaly_count_24h,
    AVG(sm.cpu_utilization) as avg_cpu_24h,
    AVG(sm.memory_utilization) as avg_memory_24h,
    AVG(sm.latency_ms) as avg_latency_24h,
    MAX(sm.timestamp) as last_metric_timestamp
FROM foda.service_registry sr
LEFT JOIN foda.service_metrics sm ON sr.service_id = sm.service_id
    AND sm.timestamp > NOW() - INTERVAL '24 hours'
LEFT JOIN foda.diagnostic_events de ON sr.service_id = de.service_id
    AND de.timestamp > NOW() - INTERVAL '24 hours'
GROUP BY sr.service_id, sr.service_name, sr.status;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA foda TO foda_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA foda TO foda_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA foda TO foda_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA foda TO foda_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA foda GRANT ALL ON TABLES TO foda_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA foda GRANT ALL ON SEQUENCES TO foda_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA foda GRANT ALL ON FUNCTIONS TO foda_user;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'FODA database initialized successfully!';
END $$;
