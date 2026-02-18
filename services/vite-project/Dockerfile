# Build stage
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY . .
RUN npx vite build

# Runtime stage
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8082
CMD ["nginx", "-g", "daemon off;"]
