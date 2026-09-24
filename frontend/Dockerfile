# syntax=docker/dockerfile:1
FROM node:22-alpine AS build

WORKDIR /app

# Same-origin by default: nginx (below) proxies /api/* to the backend.
ARG VITE_API_BASE_URL=/api
ARG VITE_STRIPE_PUBLISHABLE_KEY
# Empty means "use the built-in default"; see frontend/src/shared/map/config.ts.
ARG VITE_MAP_TILE_URL
ARG VITE_MAP_DEFAULT_CENTER
ARG VITE_MAP_ATTRIBUTION
ARG VITE_TELEGRAM_BOT_USERNAME
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_STRIPE_PUBLISHABLE_KEY=$VITE_STRIPE_PUBLISHABLE_KEY
ENV VITE_MAP_TILE_URL=$VITE_MAP_TILE_URL
ENV VITE_MAP_DEFAULT_CENTER=$VITE_MAP_DEFAULT_CENTER
ENV VITE_MAP_ATTRIBUTION=$VITE_MAP_ATTRIBUTION
ENV VITE_TELEGRAM_BOT_USERNAME=$VITE_TELEGRAM_BOT_USERNAME

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
