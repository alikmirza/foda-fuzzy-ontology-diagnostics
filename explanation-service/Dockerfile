# Multi-stage Dockerfile for FODA Explanation Service
FROM maven:3.9.5-eclipse-temurin-17 AS builder

WORKDIR /build

# Copy parent pom first for dependency caching
COPY pom.xml /build/pom.xml

# Copy module pom
COPY explanation-service/pom.xml /build/explanation-service/pom.xml

# Download dependencies
RUN mvn dependency:go-offline -pl explanation-service -am --no-transfer-progress 2>/dev/null || true

# Copy source
COPY explanation-service/src /build/explanation-service/src

# Build
RUN mvn clean package -pl explanation-service -DskipTests --no-transfer-progress

# Runtime stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Add non-root user for security
RUN addgroup -S foda && adduser -S foda -G foda

COPY --from=builder /build/explanation-service/target/explanation-service-*.jar app.jar

RUN chown foda:foda app.jar
USER foda

EXPOSE 8086

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget -q -O - http://localhost:8086/explanation/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
