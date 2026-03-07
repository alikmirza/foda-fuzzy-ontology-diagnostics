package com.foda.ontology.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@Slf4j
@RequiredArgsConstructor
public class SparqlQueryService {

    private final FusekiService fusekiService;

    private static final String NS = "http://foda.com/ontology/diagnostic#";
    private static final String DATA_NS = "http://foda.com/data/diagnostic#";

    /**
     * Get all diagnostics for a service
     */
    public List<Map<String, String>> getDiagnosticsByService(String serviceId) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?diagnosticId ?timestamp ?faultType ?severity ?fci
            WHERE {
                ?service diagnostic:serviceId "%s" .
                ?service diagnostic:hasDiagnosis ?diagnostic .
                ?diagnostic diagnostic:diagnosticId ?diagnosticId .
                ?diagnostic diagnostic:timestamp ?timestamp .
                ?diagnostic diagnostic:diagnosedAs ?fault .
                ?diagnostic diagnostic:hasSeverity ?sev .
                ?diagnostic diagnostic:fci ?fci .
                ?fault rdf:type ?faultType .
                ?sev rdf:type diagnostic:Severity .
                BIND(STRAFTER(STR(?sev), "#") AS ?severity)
            }
            ORDER BY DESC(?timestamp)
            """, NS, DATA_NS, serviceId);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get diagnostics by fault type
     */
    public List<Map<String, String>> getDiagnosticsByFaultType(String faultType) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?diagnosticId ?serviceId ?timestamp ?severity ?fci
            WHERE {
                ?diagnostic diagnostic:diagnosticId ?diagnosticId .
                ?diagnostic diagnostic:timestamp ?timestamp .
                ?diagnostic diagnostic:fci ?fci .
                ?diagnostic diagnostic:diagnosedAs diagnostic:%s .
                ?diagnostic diagnostic:hasSeverity ?sev .
                ?service diagnostic:hasDiagnosis ?diagnostic .
                ?service diagnostic:serviceId ?serviceId .
                BIND(STRAFTER(STR(?sev), "#") AS ?severity)
            }
            ORDER BY DESC(?timestamp)
            """, NS, DATA_NS, faultType);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get diagnostics by severity
     */
    public List<Map<String, String>> getDiagnosticsBySeverity(String severity) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?diagnosticId ?serviceId ?timestamp ?faultType ?fci
            WHERE {
                ?diagnostic diagnostic:diagnosticId ?diagnosticId .
                ?diagnostic diagnostic:timestamp ?timestamp .
                ?diagnostic diagnostic:fci ?fci .
                ?diagnostic diagnostic:hasSeverity diagnostic:%s .
                ?diagnostic diagnostic:diagnosedAs ?fault .
                ?service diagnostic:hasDiagnosis ?diagnostic .
                ?service diagnostic:serviceId ?serviceId .
                ?fault rdf:type ?faultType .
                FILTER(?faultType != <http://foda.com/ontology/diagnostic#Fault>)
            }
            ORDER BY DESC(?timestamp)
            """, NS, DATA_NS, severity);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get recommendations for a diagnostic
     */
    public List<Map<String, String>> getRecommendations(String diagnosticId) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?label ?description
            WHERE {
                ?diagnostic diagnostic:diagnosticId "%s" .
                ?diagnostic diagnostic:diagnosedAs ?faultType .
                ?fault rdf:type ?faultType .
                ?fault diagnostic:hasRecommendation ?rec .
                ?rec rdfs:label ?label .
                ?rec diagnostic:description ?description .
            }
            """, NS, DATA_NS, diagnosticId);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get contributing factors for a diagnostic
     */
    public List<Map<String, String>> getContributingFactors(String diagnosticId) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?metricName ?metricValue ?importance ?description
            WHERE {
                ?diagnostic diagnostic:diagnosticId "%s" .
                ?diagnostic diagnostic:diagnosedAs ?faultType .
                ?fault rdf:type ?faultType .
                ?fault diagnostic:hasContributingFactor ?factor .
                ?factor diagnostic:metricName ?metricName .
                ?factor diagnostic:metricValue ?metricValue .
                ?factor diagnostic:importance ?importance .
                ?factor diagnostic:description ?description .
            }
            ORDER BY DESC(?importance)
            """, NS, DATA_NS, diagnosticId);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get diagnostic details
     */
    public Map<String, String> getDiagnosticDetails(String diagnosticId) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?serviceId ?timestamp ?faultType ?severity ?fci ?confidence ?description
            WHERE {
                ?diagnostic diagnostic:diagnosticId "%s" .
                ?diagnostic diagnostic:timestamp ?timestamp .
                ?diagnostic diagnostic:fci ?fci .
                ?diagnostic diagnostic:confidence ?confidence .
                ?diagnostic diagnostic:description ?description .
                ?diagnostic diagnostic:diagnosedAs ?fault .
                ?diagnostic diagnostic:hasSeverity ?sev .
                ?service diagnostic:hasDiagnosis ?diagnostic .
                ?service diagnostic:serviceId ?serviceId .
                ?fault rdf:type ?faultType .
                FILTER(?faultType != <http://foda.com/ontology/diagnostic#Fault>)
                BIND(STRAFTER(STR(?sev), "#") AS ?severity)
            }
            """, NS, DATA_NS, diagnosticId);

        List<Map<String, String>> results = fusekiService.executeQuery(query);
        return results.isEmpty() ? null : results.get(0);
    }

    /**
     * Get fault statistics
     */
    public List<Map<String, String>> getFaultStatistics() {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?faultType (COUNT(?diagnostic) AS ?count)
            WHERE {
                ?diagnostic diagnostic:diagnosedAs ?fault .
                ?fault rdf:type ?faultType .
                FILTER(?faultType != <http://foda.com/ontology/diagnostic#Fault>)
            }
            GROUP BY ?faultType
            ORDER BY DESC(?count)
            """, NS, DATA_NS);

        return fusekiService.executeQuery(query);
    }

    /**
     * Get recent diagnostics
     */
    public List<Map<String, String>> getRecentDiagnostics(int limit) {
        String query = String.format("""
            PREFIX diagnostic: <%s>
            PREFIX data: <%s>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?diagnosticId ?serviceId ?timestamp ?faultType ?severity ?fci
            WHERE {
                ?diagnostic diagnostic:diagnosticId ?diagnosticId .
                ?diagnostic diagnostic:timestamp ?timestamp .
                ?diagnostic diagnostic:fci ?fci .
                ?diagnostic diagnostic:diagnosedAs ?fault .
                ?diagnostic diagnostic:hasSeverity ?sev .
                ?service diagnostic:hasDiagnosis ?diagnostic .
                ?service diagnostic:serviceId ?serviceId .
                ?fault rdf:type ?faultType .
                FILTER(?faultType != <http://foda.com/ontology/diagnostic#Fault>)
                BIND(STRAFTER(STR(?sev), "#") AS ?severity)
            }
            ORDER BY DESC(?timestamp)
            LIMIT %d
            """, NS, DATA_NS, limit);

        return fusekiService.executeQuery(query);
    }
}
