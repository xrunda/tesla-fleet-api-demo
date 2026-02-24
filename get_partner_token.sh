#!/usr/bin/env bash
# 中国区合作伙伴令牌：用 auth.tesla.cn 取 token，再注册 partner_accounts
# 使用方式：先设置环境变量或直接改下面两行后执行 bash get_partner_token.sh

set -e
CLIENT_ID="${CLIENT_ID:-29357fd6-434e-4d3b-a305-bb63a65d9f55}"
CLIENT_SECRET="${CLIENT_SECRET:-ta-secret.syUH05HKiN++h+xN}"
AUDIENCE='https://fleet-api.prd.cn.vn.cloud.tesla.cn'
TOKEN_URL='https://auth.tesla.cn/oauth2/v3/token'

echo "=== 请求 token (POST $TOKEN_URL) ==="
response=$(curl -s -w "\n%{http_code}" --request POST --ssl-no-revoke \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode 'scope=openid vehicle_device_data' \
  --data-urlencode "audience=$AUDIENCE" \
  "$TOKEN_URL")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
echo "HTTP 状态码: $http_code"
echo "响应体:"
echo "$body" | jq . 2>/dev/null || echo "$body"

ACCESS_TOKEN=$(echo "$body" | jq -r '.access_token // empty')
if [[ -z "$ACCESS_TOKEN" || "$ACCESS_TOKEN" == "null" ]]; then
  echo ""
  echo "未获取到 access_token，请检查 CLIENT_ID/CLIENT_SECRET 及中国区应用是否已审批。"
  exit 1
fi

echo ""
echo "ACCESS_TOKEN (前 20 字符): ${ACCESS_TOKEN:0:20}..."
echo ""
echo "=== 注册 partner_accounts (POST $AUDIENCE/api/1/partner_accounts) ==="
partner_resp=$(curl -s -w "\n%{http_code}" --request POST --location "$AUDIENCE/api/1/partner_accounts" \
  --ssl-no-revoke \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer $ACCESS_TOKEN" \
  --data '{"domain": "unrebuffable-antonietta-monocled.ngrok-free.dev"}')
partner_code=$(echo "$partner_resp" | tail -n1)
partner_body=$(echo "$partner_resp" | sed '$d')
echo "HTTP 状态码: $partner_code"
echo "$partner_body" | jq . 2>/dev/null || echo "$partner_body"
