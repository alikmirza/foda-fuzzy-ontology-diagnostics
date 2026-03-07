package com.foda.explanation.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.foda.explanation.model.ExplanationResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Repository for storing and retrieving explanations from PostgreSQL.
 */
@Repository
@Slf4j
@RequiredArgsConstructor
public class ExplanationRepository {

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public void save(ExplanationResult explanation) {
        String sql = """
                INSERT INTO foda.diagnostic_events
                    (explanation_id, service_id, diagnostic_result, fuzzy_confidence,
                     ml_anomaly_score, ml_confidence, crisp_confidence,
                     causal_chain, ontology_iri, suggested_actions, provenance)
                VALUES (::uuid, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?::jsonb, ?::jsonb)
                ON CONFLICT (explanation_id) DO NOTHING
                """.replace("::", "?::").strip();

        // Use the correct SQL with proper casting
        String insertSql = "INSERT INTO foda.diagnostic_events " +
                "(explanation_id, service_id, diagnostic_result, fuzzy_confidence, " +
                "ml_anomaly_score, ml_confidence, crisp_confidence, " +
                "causal_chain, ontology_iri, suggested_actions, provenance) " +
                "VALUES (?::uuid, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?::jsonb, ?::jsonb) " +
                "ON CONFLICT (explanation_id) DO NOTHING";

        try {
            jdbcTemplate.update(insertSql,
                    explanation.getExplanationId(),
                    explanation.getServiceId(),
                    explanation.getDiagnosticResult(),
                    explanation.getFuzzyConfidence(),
                    explanation.getMlAnomalyScore(),
                    explanation.getMlConfidence(),
                    explanation.getCrispConfidence(),
                    toJson(explanation.getCausalChain()),
                    explanation.getOntologyIri(),
                    toJson(explanation.getSuggestedActions()),
                    toJson(explanation.getProvenance())
            );
            log.debug("Saved explanation: id={}", explanation.getExplanationId());
        } catch (Exception e) {
            log.error("Failed to save explanation: id={}", explanation.getExplanationId(), e);
        }
    }

    public List<Map<String, Object>> findByServiceId(String serviceId, int limit) {
        String sql = "SELECT * FROM foda.diagnostic_events WHERE service_id = ? " +
                "ORDER BY timestamp DESC LIMIT ?";
        return jdbcTemplate.queryForList(sql, serviceId, limit);
    }

    public List<Map<String, Object>> findByFaultType(String faultType, int limit) {
        String sql = "SELECT * FROM foda.diagnostic_events WHERE diagnostic_result = ? " +
                "ORDER BY timestamp DESC LIMIT ?";
        return jdbcTemplate.queryForList(sql, faultType, limit);
    }

    public List<Map<String, Object>> findRecent(int limit) {
        String sql = "SELECT * FROM foda.diagnostic_events ORDER BY timestamp DESC LIMIT ?";
        return jdbcTemplate.queryForList(sql, limit);
    }

    public Optional<Map<String, Object>> findById(String explanationId) {
        String sql = "SELECT * FROM foda.diagnostic_events WHERE explanation_id = ?::uuid";
        List<Map<String, Object>> results = jdbcTemplate.queryForList(sql, explanationId);
        return results.isEmpty() ? Optional.empty() : Optional.of(results.get(0));
    }

    public Map<String, Object> getFaultStatistics() {
        String sql = "SELECT diagnostic_result, COUNT(*) as count, " +
                "AVG(fuzzy_confidence) as avg_confidence " +
                "FROM foda.diagnostic_events " +
                "GROUP BY diagnostic_result ORDER BY count DESC";
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql);
        return Map.of("faultDistribution", rows);
    }

    private String toJson(Object obj) {
        if (obj == null) return "{}";
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize to JSON", e);
            return "{}";
        }
    }
}
