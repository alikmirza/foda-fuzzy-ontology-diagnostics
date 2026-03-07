package com.foda.ontology.service;

import lombok.extern.slf4j.Slf4j;
import org.apache.jena.ontology.OntModel;
import org.apache.jena.ontology.OntModelSpec;
import org.apache.jena.rdf.model.ModelFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.io.InputStream;

@Service
@Slf4j
public class OntologyLoader {

    @Value("${ontology.file.path:classpath:ontology/DiagnosticKB.owl}")
    private Resource ontologyResource;

    private OntModel ontologyModel;

    @PostConstruct
    public void loadOntology() {
        try {
            log.info("Loading diagnostic ontology from: {}", ontologyResource.getFilename());

            // Create OWL ontology model
            ontologyModel = ModelFactory.createOntologyModel(OntModelSpec.OWL_MEM);

            // Load ontology file
            try (InputStream inputStream = ontologyResource.getInputStream()) {
                ontologyModel.read(inputStream, null, "RDF/XML");
            }

            log.info("Ontology loaded successfully. Triples count: {}", ontologyModel.size());
            log.info("Ontology base URI: {}", ontologyModel.getNsPrefixURI(""));

        } catch (Exception e) {
            log.error("Failed to load ontology", e);
            throw new RuntimeException("Failed to load diagnostic ontology", e);
        }
    }

    public OntModel getOntologyModel() {
        return ontologyModel;
    }

    public String getOntologyNamespace() {
        return "http://foda.com/ontology/diagnostic#";
    }
}
