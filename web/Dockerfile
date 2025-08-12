## Web Dockerfile (production)
FROM node:20-alpine AS deps

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --omit=dev || npm ci || npm install --omit=dev

FROM node:20-alpine AS builder
WORKDIR /app/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/web/node_modules ./node_modules
COPY web .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=builder /app/web/.next ./.next
COPY --from=builder /app/web/public ./public
COPY --from=builder /app/web/package.json ./package.json
COPY --from=builder /app/web/node_modules ./node_modules

WORKDIR /app/web

COPY web/package*.json ./
RUN npm ci || npm install

COPY web .

ENV PORT=3000 \
    HOSTNAME=0.0.0.0

EXPOSE 3000

CMD ["npm", "run", "start"]


