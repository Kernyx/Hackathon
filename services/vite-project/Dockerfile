# Build stage
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npx vite build

# Runtime stage — nginx для отдачи статики
FROM nginx:1.27-alpine

# Удаляем дефолтный конфиг и добавляем свой
RUN rm /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

# Конфиг nginx: SPA fallback + health endpoint
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 8082;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Health endpoint
    location /health {
        access_log off;
        return 200 'OK';
        add_header Content-Type text/plain;
    }

    # SPA fallback: все пути → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Кэширование статики
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 256;
}
EOF

EXPOSE 8082
CMD ["nginx", "-g", "daemon off;"]
