package com.foda.ontology.kafka;

import com.foda.ontology.model.DiagnosticResult;
import com.foda.ontology.service.DiagnosticMapper;
import com.foda.ontology.service.FusekiService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.jena.rdf.model.Model;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@Slf4j
@RequiredArgsConstructor
public class DiagnosticConsumer {

    private final DiagnosticMapper diagnosticMapper;
    private final FusekiService fusekiService;

    @KafkaListener(
            topics = "${kafka.topic.diagnostic-events}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "diagnosticKafkaListenerContainerFactory"
    )
    public void consumeDiagnostic(DiagnosticResult diagnostic) {
        try {
            log.info("Received diagnostic event: service={}, diagnosticId={}, fault={}",
                    diagnostic.getServiceId(),
                    diagnostic.getDiagnosticId(),
                    diagnostic.getFaultType());

            // Map diagnostic to RDF
            Model rdfModel = diagnosticMapper.mapToRDF(diagnostic);

            // Store in Fuseki
            fusekiService.storeModel(rdfModel);

            log.info("Diagnostic {} successfully stored in triple store", diagnostic.getDiagnosticId());

        } catch (Exception e) {
            log.error("Error processing diagnostic event: diagnosticId={}",
                    diagnostic.getDiagnosticId(), e);
        }
    }
}
