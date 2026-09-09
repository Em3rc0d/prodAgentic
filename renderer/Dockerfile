FROM mcr.microsoft.com/playwright:v1.62.1-noble

WORKDIR /app

ENV NODE_ENV=production \
    PORT=4100 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Reuse the repository's locked Playwright dependency graph. The renderer has
# no independent package drift: its browser client version is the same one CI
# already certifies in frontend/package-lock.json.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY renderer/src ./src

USER pwuser
EXPOSE 4100

CMD ["node", "src/server.mjs"]
