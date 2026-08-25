FROM node:22-alpine AS builder

WORKDIR /workspace/apps/frontend
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci

WORKDIR /workspace
COPY apps/frontend ./apps/frontend
COPY data/demo ./data/demo

WORKDIR /workspace/apps/frontend
RUN npm run build \
    && npm prune --omit=dev

FROM node:22-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 --ingroup nodejs nextjs

WORKDIR /workspace/apps/frontend
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/frontend ./
COPY --from=builder --chown=nextjs:nodejs /workspace/data /workspace/data

USER nextjs
EXPOSE 3000
CMD ["npm", "run", "start"]
