# STAGE 1: сборка
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

# STAGE 2: запуск
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app .
EXPOSE 8082
CMD ["npm", "start"]
