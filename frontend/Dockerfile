# --- dev: vite dev server с HMR, код приходит bind-mount'ом ---
FROM node:20-alpine AS dev
ARG UID=1000
ARG GID=1000
# В образе уже есть пользователь node (1000:1000) — подгоняем под id хоста,
# чтобы файлы в bind-mount не оказывались под root
RUN apk add --no-cache shadow \
 && groupmod -o -g ${GID} node \
 && usermod -o -u ${UID} -g ${GID} node \
 && chown -R node:node /home/node

WORKDIR /app
COPY --chown=node:node package.json package-lock.json ./
USER node
RUN npm ci
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --- build: собираем статику ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- prod: nginx отдаёт статику и проксирует /api ---
FROM nginx:alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
