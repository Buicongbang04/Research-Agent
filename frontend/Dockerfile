# syntax=docker/dockerfile:1.7

# ────── Build stage ──────
FROM node:22-alpine AS builder
WORKDIR /app

# Build-time env: must be present BEFORE `next build` for NEXT_PUBLIC_* to bake into the bundle
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Install deps (separate layer for cache)
COPY package.json package-lock.json* ./
RUN npm install --no-fund --no-audit

# Build standalone output
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ────── Runner stage ──────
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# Non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# Copy only the bits Next.js standalone needs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV HOSTNAME=0.0.0.0 PORT=3000

CMD ["node", "server.js"]
