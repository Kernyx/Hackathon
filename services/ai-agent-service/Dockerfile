FROM maven:3.9-eclipse-temurin-21-alpine AS builder

ARG DB_HOST=postgres
ARG DB_USERNAME
ARG DB_PASSWORD
ARG DB_NAME=hackathon_db

WORKDIR /app
COPY pom.xml ./
RUN --mount=type=cache,target=/root/.m2 \
    mvn dependency:go-offline -B

COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    mvn package -B -DskipTests \
       -Dprop.skipLoadProperties=true \
       -DDB_HOST="${DB_HOST}" \
       -DDB_USERNAME="${DB_USERNAME}" \
       -DDB_PASSWORD="${DB_PASSWORD}" \
       -DDB_NAME="${DB_NAME}"

FROM eclipse-temurin:21-jre-alpine

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

RUN chown app:app app.jar
USER app

EXPOSE 8080
ENTRYPOINT ["java", "-XX:+UseContainerSupport", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
