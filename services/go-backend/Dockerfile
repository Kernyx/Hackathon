# STAGE 1: сборка
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

# STAGE 2: запуск
FROM gcr.io/distroless/static-debian12
WORKDIR /app
COPY --from=builder /app/main .
EXPOSE 8081
ENTRYPOINT ["/app/main"]
