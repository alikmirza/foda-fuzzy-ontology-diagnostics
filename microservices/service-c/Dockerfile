# Dockerfile for Service-C - using pre-built JAR

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

# Create non-root user
RUN addgroup -S foda && adduser -S foda -G foda

# Copy the pre-built JAR
COPY microservices/service-c/target/service-c-1.0.0-SNAPSHOT.jar app.jar

RUN chown -R foda:foda /app
USER foda

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/status/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "-Xmx512m", "-Xms256m", "app.jar"]
