# Build stage
FROM golang:1.24-alpine AS builder
<<<<<<< HEAD
=======

RUN apk add --no-cache git

>>>>>>> origin/frontend
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
<<<<<<< HEAD
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main ./cmd
=======
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w" \
    -trimpath \
    -o main ./cmd
>>>>>>> origin/frontend

# Runtime stage
FROM alpine:3.21

RUN apk add --no-cache ca-certificates wget \
    && addgroup -S app && adduser -S app -G app

COPY --from=builder /app/main /main

USER app
EXPOSE 8083
ENTRYPOINT ["/main"]
