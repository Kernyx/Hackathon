# Build stage
FROM caddy:2.10-builder-alpine AS builder

ENV GOPROXY=https://proxy.golang.org,direct \
    GOSUMDB=off

RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit

# Runtime stage
FROM caddy:2.10-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
