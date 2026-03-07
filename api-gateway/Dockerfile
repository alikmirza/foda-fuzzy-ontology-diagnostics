# Multi-stage build for API Gateway
FROM eclipse-temurin:17-jdk-alpine AS build

WORKDIR /app

# Copy parent POM and api-gateway POM
COPY pom.xml ./
COPY api-gateway/pom.xml ./api-gateway/

# Copy source code
COPY api-gateway/src ./api-gateway/src

# Build the application
RUN apk add --no-cache maven && \
    mvn -f api-gateway/pom.xml clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Copy the built JAR
COPY --from=build /app/api-gateway/target/*.jar app.jar

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
