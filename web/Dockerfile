## Web Dockerfile (production)
FROM node:20-alpine AS deps

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --omit=dev || npm ci || npm install --omit=dev

FROM node:20-alpine AS builder
WORKDIR /app/web
ENV NEXT_TELEMETRY_DISABLED=1
# Accept build-time overrides for API origins so Next.js can bake them during `next build`
ARG NEXT_PUBLIC_API_URL
ARG API_INTERNAL_ORIGIN
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV API_INTERNAL_ORIGIN=${API_INTERNAL_ORIGIN}
COPY --from=deps /app/web/node_modules ./node_modules
COPY web .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# Keep envs available at runtime as well (not strictly required for Next, but useful for tooling)
ARG NEXT_PUBLIC_API_URL
ARG API_INTERNAL_ORIGIN
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV API_INTERNAL_ORIGIN=${API_INTERNAL_ORIGIN}
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


