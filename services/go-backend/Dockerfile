# Build stage
FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod download

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -o main ./cmd

# Runtime stage
FROM alpine:3.21

RUN apk add --no-cache ca-certificates wget redis \
    && addgroup -S app && adduser -S app -G app

COPY --from=builder /app/main /main

USER app
EXPOSE 8083
ENTRYPOINT ["/main"]
