# Dockerfile for Fuzzy Engine - using pre-built JAR

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

# Create non-root user
RUN addgroup -S foda && adduser -S foda -G foda

# Copy the pre-built JAR
COPY fuzzy-engine/target/fuzzy-engine-1.0.0-SNAPSHOT.jar app.jar

RUN chown -R foda:foda /app
USER foda

# Expose port
EXPOSE 8084

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8084/fuzzy/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
