# Image development untuk compose. Produksi di-deploy ke Vercel, tidak lewat image ini.
FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# UID node (1000) harus sama dengan user host supaya bisa menulis ke bind mount ./web.
RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
