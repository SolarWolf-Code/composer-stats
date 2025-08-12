# Web Dockerfile (dev mode)
FROM node:20-alpine

WORKDIR /app/web

COPY web/package*.json ./
RUN npm ci || npm install

COPY web .

ENV PORT=3000 \
    HOSTNAME=0.0.0.0

EXPOSE 3000

CMD ["npm", "run", "dev"]


