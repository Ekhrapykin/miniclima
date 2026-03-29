# Stage 1 — build
FROM node:25-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Copy source — explicit list avoids pulling in host node_modules (no .dockerignore needed)
COPY app ./app
COPY public ./public
COPY next.config.ts tsconfig.json postcss.config.mjs eslint.config.mjs ./

# NEXT_PUBLIC_* vars are baked in at build time — pass via --build-arg
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Turbopack has no ARM native bindings — use webpack on ARM/linux
RUN npm run build -- --webpack

# Stage 2 — runtime (standalone output only, no node_modules)
FROM node:25-slim AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

RUN useradd -m appuser
USER appuser

EXPOSE 3000

CMD ["node", "server.js"]
