# Build stage
FROM maven:3.9-eclipse-temurin-21-alpine AS builder

ARG DB_HOST=postgres
ARG DB_USERNAME
ARG DB_PASSWORD
ARG DB_NAME=hackathon_db

WORKDIR /app
COPY . .

RUN mvn dependency:go-offline -B

RUN mvn package -B -DskipTests \
       -Dprop.skipLoadProperties=true \
       -DDB_HOST="${DB_HOST}" \
       -DDB_USERNAME="${DB_USERNAME}" \
       -DDB_PASSWORD="${DB_PASSWORD}" \
       -DDB_NAME="${DB_NAME}"

# Runtime stage
FROM eclipse-temurin:21-jre-alpine

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

RUN mkdir -p /app/keys && chown -R app:app /app
USER app

EXPOSE 8081
ENTRYPOINT ["java", "-XX:+UseContainerSupport", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
