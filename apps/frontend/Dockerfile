FROM node:20-alpine AS base

# Install pnpm via corepack (Node ships it built-in)
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# Capping Node heap to 768MB (container cap is 1GB, leaving 256MB for the
# rest of the process — buffers, native modules, Turbopack workers).
ENV NODE_OPTIONS="--max-old-space-size=768"

WORKDIR /app

# Install dependencies (cached layer)
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# Copy source
COPY . .

EXPOSE 3000

CMD ["pnpm", "dev"]
