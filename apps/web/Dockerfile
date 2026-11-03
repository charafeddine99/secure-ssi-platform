FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Empty = same-origin /api through this image's nginx proxy (recommended).
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run lint
RUN npm run build

FROM nginx:1.27-alpine
ARG VITE_API_BASE_URL=
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Allow the browser to call only this origin besides itself (CSP connect-src).
RUN API_ORIGIN="$(echo "$VITE_API_BASE_URL" | sed -E 's#^(https?://[^/]+).*#\1#')" \
    && sed -i "s#__API_ORIGIN__#${API_ORIGIN}#" /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD wget -q --spider http://127.0.0.1/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
