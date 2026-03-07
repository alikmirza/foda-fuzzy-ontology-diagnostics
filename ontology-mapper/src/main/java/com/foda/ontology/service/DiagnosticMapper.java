package com.foda.ontology.service;

import com.foda.ontology.model.DiagnosticResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.jena.rdf.model.*;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.format.DateTimeFormatter;

@Service
@Slf4j
@RequiredArgsConstructor
public class DiagnosticMapper {

    private final OntologyLoader ontologyLoader;

    private static final String NS = "http://foda.com/ontology/diagnostic#";
    private static final String DATA_NS = "http://foda.com/data/diagnostic#";

    /**
     * Convert DiagnosticResult to RDF Model
     */
    public Model mapToRDF(DiagnosticResult diagnostic) {
        try {
            // Create new model for this diagnostic
            Model model = ModelFactory.createDefaultModel();
            model.setNsPrefix("diagnostic", NS);
            model.setNsPrefix("data", DATA_NS);

            // Create resources
            Resource diagnosticRes = model.createResource(DATA_NS + "diagnostic_" + diagnostic.getDiagnosticId());
            Resource serviceRes = model.createResource(DATA_NS + "service_" + diagnostic.getServiceId());
            Resource anomalyRes = model.createResource(DATA_NS + "anomaly_" + diagnostic.getPredictionId());
            Resource faultTypeRes = model.createResource(NS + convertFaultType(diagnostic.getFaultType()));
            Resource severityRes = model.createResource(NS + diagnostic.getSeverity());

            // Service instance
            serviceRes.addProperty(RDF.type, model.createResource(NS + "MicroService"))
                    .addProperty(model.createProperty(NS + "serviceId"), diagnostic.getServiceId())
                    .addProperty(model.createProperty(NS + "hasDiagnosis"), diagnosticRes);

            // Anomaly
            anomalyRes.addProperty(RDF.type, model.createResource(NS + "Anomaly"))
                    .addProperty(model.createProperty(NS + "predictionId"), diagnostic.getPredictionId())
                    .addProperty(model.createProperty(NS + "anomalyScore"),
                               model.createTypedLiteral(diagnostic.getMlAnomalyScore()))
                    .addProperty(model.createProperty(NS + "timestamp"),
                               model.createTypedLiteral(diagnostic.getTimestamp()))
                    .addProperty(model.createProperty(NS + "diagnosedAs"), faultTypeRes)
                    .addProperty(model.createProperty(NS + "detectedBy"),
                               model.createResource(DATA_NS + "model_ensemble"));

            // Diagnostic Result
            diagnosticRes.addProperty(RDF.type, model.createResource(NS + "DiagnosticResult"))
                    .addProperty(model.createProperty(NS + "diagnosticId"), diagnostic.getDiagnosticId())
                    .addProperty(model.createProperty(NS + "confidence"),
                               model.createTypedLiteral(diagnostic.getMlConfidence()))
                    .addProperty(model.createProperty(NS + "fci"),
                               model.createTypedLiteral(diagnostic.getFci()))
                    .addProperty(model.createProperty(NS + "timestamp"),
                               model.createTypedLiteral(diagnostic.getTimestamp()))
                    .addProperty(model.createProperty(NS + "description"),
                               diagnostic.getFaultDescription());

            // Link diagnostic to fault and severity
            diagnosticRes.addProperty(model.createProperty(NS + "diagnosedAs"), faultTypeRes);
            diagnosticRes.addProperty(model.createProperty(NS + "hasSeverity"), severityRes);

            // Fault
            Resource faultInstance = model.createResource(DATA_NS + "fault_" + diagnostic.getDiagnosticId());
            faultInstance.addProperty(RDF.type, faultTypeRes)
                    .addProperty(model.createProperty(NS + "affectsService"), serviceRes)
                    .addProperty(model.createProperty(NS + "hasSeverity"), severityRes)
                    .addProperty(model.createProperty(NS + "timestamp"),
                               model.createTypedLiteral(diagnostic.getTimestamp()));

            // Contributing factors
            if (diagnostic.getContributingFactors() != null) {
                for (int i = 0; i < diagnostic.getContributingFactors().size(); i++) {
                    DiagnosticResult.ContributingFactor factor = diagnostic.getContributingFactors().get(i);
                    Resource factorRes = model.createResource(
                            DATA_NS + "factor_" + diagnostic.getDiagnosticId() + "_" + i);

                    factorRes.addProperty(RDF.type, model.createResource(NS + "ContributingFactor"))
                            .addProperty(RDFS.label, factor.getMetric())
                            .addProperty(model.createProperty(NS + "metricName"), factor.getMetric())
                            .addProperty(model.createProperty(NS + "metricValue"),
                                       model.createTypedLiteral(factor.getValue()))
                            .addProperty(model.createProperty(NS + "importance"),
                                       model.createTypedLiteral(factor.getImportance()))
                            .addProperty(model.createProperty(NS + "description"),
                                       factor.getInterpretation());

                    faultInstance.addProperty(model.createProperty(NS + "hasContributingFactor"), factorRes);
                }
            }

            // Recommendations
            if (diagnostic.getRecommendations() != null) {
                for (int i = 0; i < diagnostic.getRecommendations().size(); i++) {
                    String recommendation = diagnostic.getRecommendations().get(i);
                    Resource recRes = model.createResource(
                            DATA_NS + "recommendation_" + diagnostic.getDiagnosticId() + "_" + i);

                    recRes.addProperty(RDF.type, model.createResource(NS + "Recommendation"))
                            .addProperty(model.createProperty(NS + "description"), recommendation)
                            .addProperty(RDFS.label, "Recommendation " + (i + 1));

                    faultInstance.addProperty(model.createProperty(NS + "hasRecommendation"), recRes);
                }
            }

            // Fuzzy memberships as metrics
            if (diagnostic.getFuzzyMemberships() != null) {
                diagnostic.getFuzzyMemberships().forEach((metricName, value) -> {
                    Resource metricRes = model.createResource(
                            DATA_NS + "metric_" + diagnostic.getDiagnosticId() + "_" + metricName);

                    metricRes.addProperty(RDF.type, model.createResource(NS + "Metric"))
                            .addProperty(model.createProperty(NS + "metricName"), "fuzzy_" + metricName)
                            .addProperty(model.createProperty(NS + "metricValue"),
                                       model.createTypedLiteral(value));

                    diagnosticRes.addProperty(model.createProperty(NS + "hasMetric"), metricRes);
                });
            }

            log.info("Mapped diagnostic {} to RDF model with {} triples",
                    diagnostic.getDiagnosticId(), model.size());

            return model;

        } catch (Exception e) {
            log.error("Error mapping diagnostic to RDF", e);
            throw new RuntimeException("Failed to map diagnostic to RDF", e);
        }
    }

    /**
     * Convert fault type to match ontology individuals
     */
    private String convertFaultType(String faultType) {
        if (faultType == null) return "Unknown";

        // Convert from UPPER_SNAKE_CASE to PascalCase
        String[] parts = faultType.split("_");
        StringBuilder result = new StringBuilder();
        for (String part : parts) {
            result.append(part.substring(0, 1).toUpperCase())
                  .append(part.substring(1).toLowerCase());
        }
        return result.toString();
    }
}
