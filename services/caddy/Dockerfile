FROM caddy:2.10-builder-alpine AS builder

ENV GOPROXY=https://proxy.golang.org,direct \
    GONOSUMDB=* \
    GOFLAGS=-trimpath

RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit

FROM caddy:2.10-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
