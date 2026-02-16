FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /app
COPY . .

WORKDIR /app/services/ai-agent-service

RUN mvn dependency:go-offline

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /app/services/ai-agent-service/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
