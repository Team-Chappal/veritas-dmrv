# VERITAS dMRV — frontend image
#
# NEXT_PUBLIC_* is INLINED AT BUILD TIME by Next.js, not read at runtime. So the
# API URL has to be a build ARG and cannot be changed by editing docker-compose
# after the fact -- the image would keep the URL it was built with.
#
# That is a real constraint rather than a Dockerfile quirk, and it is why the
# compose file builds the frontend with the API URL as an explicit build arg
# instead of passing it as an environment variable. It is also why the frontend
# image serves the demo with the API reachable at a fixed hostname.

FROM node:22-slim AS deps

WORKDIR /app
# The lockfile is committed, so `npm ci` is what runs -- an unpinned install
# would make the image differ from CI for reasons nobody would notice.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund


FROM node:22-slim AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./

# Baked in at build time. The default points at the compose service name, which
# resolves on the compose network but not from a browser on the host -- so the
# value is overridden to a localhost port for the published container.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build


FROM node:22-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
RUN useradd --create-home --uid 10002 veritas

# Only what `next start` needs: the production build, node_modules, and the
# public/ directory the service worker is served from.
COPY --from=builder --chown=veritas:veritas /app/.next ./.next
COPY --from=builder --chown=veritas:veritas /app/public ./public
COPY --from=builder --chown=veritas:veritas /app/node_modules ./node_modules
COPY --from=builder --chown=veritas:veritas /app/package.json ./package.json
COPY --from=builder --chown=veritas:veritas /app/next.config.mjs ./next.config.mjs

USER veritas
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["npm", "run", "start", "--", "--port", "3000", "--hostname", "0.0.0.0"]
