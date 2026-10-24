FROM node:26.12.0-alpine3.24 AS base
RUN npm install --global pnpm@12.15.0
WORKDIR /srv/web

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

FROM base AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:26.12.0-alpine3.24
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /srv/web
RUN addgroup -S -g 10001 web && adduser -S -u 10001 -G web web
COPY --from=build --chown=web:web /srv/web/.next/standalone ./
COPY --from=build --chown=web:web /srv/web/.next/static ./.next/static
COPY --from=build --chown=web:web /srv/web/public ./public
USER web
EXPOSE 3000
CMD ["node", "server.js"]
