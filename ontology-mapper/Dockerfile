# Multi-stage build for Ontology Mapper
FROM eclipse-temurin:17-jdk-alpine AS build

WORKDIR /app

# Copy parent POM and ontology-mapper POM
COPY pom.xml ./
COPY ontology-mapper/pom.xml ./ontology-mapper/

# Copy source code
COPY ontology-mapper/src ./ontology-mapper/src

# Copy ontology file
COPY ontology ./ontology

# Build the application
RUN apk add --no-cache maven && \
    mvn -f ontology-mapper/pom.xml clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Copy the built JAR
COPY --from=build /app/ontology-mapper/target/*.jar app.jar

# Copy ontology resources
COPY --from=build /app/ontology /ontology

# Expose port
EXPOSE 8085

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8085/ontology/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
