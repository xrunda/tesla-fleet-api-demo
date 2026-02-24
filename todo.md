317423621@qq.com

https://unrebuffable-antonietta-monocled.ngrok-free.dev\
https://unrebuffable-antonietta-monocled.ngrok-free.dev/auth/callback


29357fd6-434e-4d3b-a305-bb63a65d9f55

ta-secret.syUH05HKiN++h+xN


CLIENT_ID='29357fd6-434e-4d3b-a305-bb63a65d9f55'
CLIENT_SECRET='ta-secret.syUH05HKiN++h+xN'
AUDIENCE='https://fleet-api.prd.cn.vn.cloud.tesla.cn'
TOKEN_URL='https://auth.tesla.cn/oauth2/v3/token'

response=$(curl -s --request POST --ssl-no-revoke \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode 'scope=openid vehicle_device_data' \
  --data-urlencode "audience=$AUDIENCE" \
  "$TOKEN_URL")
echo "$response" | jq .
ACCESS_TOKEN=$(echo "$response" | jq -r '.access_token')

curl --location "$AUDIENCE/api/1/partner_accounts" \
  --ssl-no-revoke \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer $ACCESS_TOKEN" \
  --data '{"domain": "unrebuffable-antonietta-monocled.ngrok-free.dev"}'