# 阶段 1：编译 Linux 版 tesla-http-proxy（官方仓库无预编译 Linux 二进制）
FROM golang:1.23-alpine AS proxy-builder
RUN apk add --no-cache git ca-certificates
WORKDIR /build
ARG VEHICLE_COMMAND_TAG=v0.4.1
RUN git clone --depth 1 --branch "${VEHICLE_COMMAND_TAG}" https://github.com/teslamotors/vehicle-command.git .
RUN CGO_ENABLED=0 go build -o tesla-http-proxy ./cmd/tesla-http-proxy

# 阶段 2：Flask 应用 + 使用上面编译的 Linux proxy
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 镜像内 proxy 仅使用多阶段构建的 Linux 版（仓库不再包含二进制）
RUN mkdir -p /app/http_proxy
COPY --from=proxy-builder /build/tesla-http-proxy /app/http_proxy/tesla-http-proxy
RUN chmod +x /app/http_proxy/tesla-http-proxy

# 按 README：先启动 proxy（若挂载了 config），再启动 Flask
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh
RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 4443 8080

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
