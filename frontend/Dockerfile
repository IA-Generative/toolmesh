# syntax=docker/dockerfile:1
FROM oven/bun:1 AS build
WORKDIR /app
COPY package.json bun.lock ./
# The DSFR postinstall copies assets into `public/`, so it runs once the sources are there.
RUN bun install --frozen-lockfile --ignore-scripts
COPY . .
RUN bun run postinstall
# Empty by default: the SPA calls `/api` on its own origin, where the Ingress routes it to the backend.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN bun run build

FROM nginxinc/nginx-unprivileged:1-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://localhost:8080/ || exit 1
