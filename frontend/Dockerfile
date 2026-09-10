FROM node:24-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ARG NEXT_PUBLIC_MK1_SHELL=true
ARG NEXT_PUBLIC_MK1_PROFILE_V2=true
ARG NEXT_PUBLIC_MK1_BATCH_PLANNING=true
ARG NEXT_PUBLIC_MK1_MANUAL_EXPORT=false
ARG NEXT_PUBLIC_MK1_PUBLISHING=false
ARG NEXT_PUBLIC_MK1_ANALYTICS=false
ARG PRODAGENTIC_ALLOW_PRIVATE_HTTP_API=false

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_MK1_SHELL=${NEXT_PUBLIC_MK1_SHELL} \
    NEXT_PUBLIC_MK1_PROFILE_V2=${NEXT_PUBLIC_MK1_PROFILE_V2} \
    NEXT_PUBLIC_MK1_BATCH_PLANNING=${NEXT_PUBLIC_MK1_BATCH_PLANNING} \
    NEXT_PUBLIC_MK1_MANUAL_EXPORT=${NEXT_PUBLIC_MK1_MANUAL_EXPORT} \
    NEXT_PUBLIC_MK1_PUBLISHING=${NEXT_PUBLIC_MK1_PUBLISHING} \
    NEXT_PUBLIC_MK1_ANALYTICS=${NEXT_PUBLIC_MK1_ANALYTICS} \
    PRODAGENTIC_ALLOW_PRIVATE_HTTP_API=${PRODAGENTIC_ALLOW_PRIVATE_HTTP_API}

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build \
    && npm prune --omit=dev

FROM node:24-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/package-lock.json ./package-lock.json
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public

USER node
EXPOSE 3000

CMD ["npm", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
