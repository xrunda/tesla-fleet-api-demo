#!/usr/bin/env bash
# 按 README 顺序：先启动 proxy（若提供 fleet-key 或完整 config），再启动 Flask。
# 官方 proxy 必须使用 TLS；若未提供 tls-key/cert，则在有 fleet-key 时自动生成自签名 TLS（适用于 Ingress 提供对外 HTTPS 的场景）。
# K8s：可通过 Volume 挂载 fleet-key.pem，或通过环境变量 FLEET_KEY_PEM（如 secretKeyRef）注入私钥内容。
set -e

CONFIG_DIR="${CONFIG_DIR:-/app/config}"
PROXY_BIN="/app/http_proxy/tesla-http-proxy"
TLS_KEY="$CONFIG_DIR/tls-key.pem"
TLS_CERT="$CONFIG_DIR/tls-cert.pem"
FLEET_KEY="$CONFIG_DIR/fleet-key.pem"

# K8s Secret 通过环境变量注入私钥时，写到临时文件（/app/config 可能为只读 Volume）
# 规范化 PEM：K8s 可能把换行变成字面 \n 或空格，导致 proxy 报 invalid private key: expected PEM encoding
if [[ -n "${FLEET_KEY_PEM:-}" && ! -f "$FLEET_KEY" ]]; then
  FLEET_KEY="/tmp/proxy-config/fleet-key.pem"
  mkdir -p "$(dirname "$FLEET_KEY")"
  content="${FLEET_KEY_PEM//\\n/$'\n'}"
  # 若为单行或空格分隔的块（K8s 常把换行变成空格），将空格改为换行；PEM base64 不含空格
  content="${content// /$'\n'}"
  echo "$content" > "$FLEET_KEY"
  chmod 600 "$FLEET_KEY"
fi

need_proxy() {
  [[ -f "$FLEET_KEY" ]]
}

ensure_tls_certs() {
  if [[ -f "$TLS_KEY" && -f "$TLS_CERT" ]]; then
    return 0
  fi
  echo "==> 未提供 TLS 证书，生成自签名证书（仅用于 Ingress→proxy 后端；对外 HTTPS 由 Ingress 提供）..."
  GEN_DIR="/tmp/proxy-tls"
  mkdir -p "$GEN_DIR"
  TLS_KEY="$GEN_DIR/tls-key.pem"
  TLS_CERT="$GEN_DIR/tls-cert.pem"
  openssl req -x509 -nodes -newkey ec \
    -pkeyopt ec_paramgen_curve:secp384r1 -pkeyopt ec_param_enc:named_curve \
    -subj '/CN=localhost' -keyout "$TLS_KEY" -out "$TLS_CERT" -sha256 -days 3650 \
    -addext "extendedKeyUsage = serverAuth" -addext "keyUsage = digitalSignature, keyAgreement" 2>/dev/null || true
  if [[ ! -f "$TLS_KEY" || ! -f "$TLS_CERT" ]]; then
    echo "==> 自签名证书生成失败，仅启动 Flask。"
    return 1
  fi
  return 0
}

if need_proxy; then
  if ensure_tls_certs; then
    echo "==> 启动 vehicle-command proxy（端口 4443）..."
    export VEHICLE_COMMAND_PROXY_BASE="${VEHICLE_COMMAND_PROXY_BASE:-https://127.0.0.1:4443}"
    export VEHICLE_COMMAND_PROXY_INSECURE="${VEHICLE_COMMAND_PROXY_INSECURE:-1}"
    "$PROXY_BIN" \
      -tls-key "$TLS_KEY" \
      -cert "$TLS_CERT" \
      -key-file "$FLEET_KEY" \
      -host 0.0.0.0 \
      -port 4443 &
    sleep 1
  fi
else
  echo "==> 未挂载 fleet-key.pem，仅启动 Flask（不启动 proxy）。"
fi

echo "==> 启动 Flask（端口 8080）..."
exec python tesla_oauth_demo.py
