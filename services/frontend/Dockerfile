FROM node:20-alpine

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app
COPY --chown=app:app server.js index.js ./

USER app
EXPOSE 8082
CMD ["node", "server.js"]
