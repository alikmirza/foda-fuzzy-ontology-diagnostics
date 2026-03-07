package com.foda.ontology.service;

import lombok.extern.slf4j.Slf4j;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdfconnection.RDFConnection;
import org.apache.jena.rdfconnection.RDFConnectionFactory;
import org.apache.jena.update.UpdateFactory;
import org.apache.jena.update.UpdateRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.StringWriter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
@Slf4j
public class FusekiService {

    @Value("${fuseki.endpoint:http://localhost:3030/foda}")
    private String fusekiEndpoint;

    /**
     * Store RDF model in Fuseki triple store
     */
    public void storeModel(Model model) {
        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            log.info("Storing model in Fuseki: {} triples", model.size());

            // Load the model into the dataset
            conn.load(model);

            log.info("Model stored successfully in Fuseki");

        } catch (Exception e) {
            log.error("Error storing model in Fuseki", e);
            throw new RuntimeException("Failed to store model in Fuseki", e);
        }
    }

    /**
     * Execute SPARQL SELECT query
     */
    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        List<Map<String, String>> results = new ArrayList<>();

        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            log.debug("Executing SPARQL query: {}", sparqlQuery);

            try (QueryExecution qExec = conn.query(sparqlQuery)) {
                ResultSet resultSet = qExec.execSelect();

                while (resultSet.hasNext()) {
                    QuerySolution solution = resultSet.nextSolution();
                    Map<String, String> row = new HashMap<>();

                    solution.varNames().forEachRemaining(varName -> {
                        if (solution.get(varName) != null) {
                            row.put(varName, solution.get(varName).toString());
                        }
                    });

                    results.add(row);
                }
            }

            log.debug("Query returned {} results", results.size());

        } catch (Exception e) {
            log.error("Error executing SPARQL query", e);
            throw new RuntimeException("Failed to execute SPARQL query", e);
        }

        return results;
    }

    /**
     * Execute SPARQL CONSTRUCT query
     */
    public Model executeConstruct(String sparqlQuery) {
        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            log.debug("Executing SPARQL CONSTRUCT query");

            try (QueryExecution qExec = conn.query(sparqlQuery)) {
                Model resultModel = qExec.execConstruct();
                log.debug("CONSTRUCT query returned {} triples", resultModel.size());
                return resultModel;
            }

        } catch (Exception e) {
            log.error("Error executing SPARQL CONSTRUCT query", e);
            throw new RuntimeException("Failed to execute SPARQL CONSTRUCT query", e);
        }
    }

    /**
     * Execute SPARQL UPDATE query
     */
    public void executeUpdate(String sparqlUpdate) {
        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            log.debug("Executing SPARQL UPDATE");

            UpdateRequest updateRequest = UpdateFactory.create(sparqlUpdate);
            conn.update(updateRequest);

            log.debug("UPDATE executed successfully");

        } catch (Exception e) {
            log.error("Error executing SPARQL UPDATE", e);
            throw new RuntimeException("Failed to execute SPARQL UPDATE", e);
        }
    }

    /**
     * Check if Fuseki is available
     */
    public boolean isAvailable() {
        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            // Simple query to test connection
            String testQuery = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }";
            try (QueryExecution qExec = conn.query(testQuery)) {
                qExec.execSelect();
                return true;
            }
        } catch (Exception e) {
            log.warn("Fuseki not available: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Get total triple count in the dataset
     */
    public long getTripleCount() {
        try (RDFConnection conn = RDFConnectionFactory.connect(fusekiEndpoint)) {
            String countQuery = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }";

            try (QueryExecution qExec = conn.query(countQuery)) {
                ResultSet results = qExec.execSelect();
                if (results.hasNext()) {
                    QuerySolution solution = results.nextSolution();
                    return solution.getLiteral("count").getLong();
                }
            }
        } catch (Exception e) {
            log.error("Error getting triple count", e);
        }
        return 0;
    }
}
