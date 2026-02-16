FROM maven:3.9-eclipse-temurin-21 AS builder

ARG DB_HOST=postgres
ARG DB_USERNAME
ARG DB_PASSWORD
ARG DB_NAME=hackathon_db

WORKDIR /app
COPY . .

WORKDIR /app/services/ai-agent-service

RUN mvn dependency:go-offline

RUN mvn package -DskipTests \
       -Dprop.skipLoadProperties=true \
       -DDB_HOST="${DB_HOST}" \
       -DDB_USERNAME="${DB_USERNAME}" \
       -DDB_PASSWORD="${DB_PASSWORD}" \
       -DDB_NAME="${DB_NAME}"

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /app/services/ai-agent-service/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
