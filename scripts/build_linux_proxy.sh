#!/usr/bin/env bash
# 在本地用 Go 交叉编译出 Linux amd64 版 tesla-http-proxy，输出到项目 http_proxy/ 目录。
# 需要已安装 Go（建议 1.23+）。可用于提交 Linux 二进制到仓库或在不建 Docker 时使用。
set -e
REPO_DIR="${REPO_DIR:-$(mktemp -d)}"
TAG="${VEHICLE_COMMAND_TAG:-v0.4.1}"
OUTPUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/http_proxy"
OUTPUT="$OUTPUT_DIR/tesla-http-proxy.linux-amd64"

echo "==> 使用 vehicle-command 版本: $TAG"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone --depth 1 --branch "$TAG" https://github.com/teslamotors/vehicle-command.git "$REPO_DIR"
else
  (cd "$REPO_DIR" && git fetch --depth 1 origin tag "$TAG" 2>/dev/null || true)
fi

(cd "$REPO_DIR" && GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o "$OUTPUT" ./cmd/tesla-http-proxy)
chmod +x "$OUTPUT"
echo "==> 已生成: $OUTPUT"
