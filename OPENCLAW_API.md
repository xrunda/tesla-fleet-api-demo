# OpenClaw API（最简集成版）

本项目已提供一组无需鉴权的 JSON API，供 OpenClaw / 飞书机器人直接调用（当前阶段先跳过鉴权）。

> Base URL：你的线上域名，例如 `https://fleet-api.dev.xrunda.com`

---

## 1) 健康检查

`GET /api/health`

返回：

```json
{
  "ok": true,
  "service": "tesla-fleet-api-demo",
  "api_version": "v1",
  "timestamp": 1700000000
}
```

## 2) 获取车辆列表

`GET /api/openclaw/vehicles`

返回：

```json
{
  "ok": true,
  "count": 1,
  "vehicles": [
    {
      "id": 366766851154357,
      "vehicle_id": 1234567890123456,
      "vin": "LRWYGCFJ0MC201432",
      "display_name": "京AAS1530",
      "state": "online"
    }
  ]
}
```

## 3) 执行车辆命令

`POST /api/openclaw/command`

请求体：

```json
{
  "command": "auto_conditioning_start",
  "vehicle_id": "366766851154357",
  "payload": {},
  "lang": "zh"
}
```

字段说明：

- `command`：必填，车辆命令名（英文）
- `vehicle_id` / `vin`：二选一，至少提供一个
- `payload`：可选，JSON 对象
- `lang`：可选，`zh` / `en`，默认 `zh`

成功返回（HTTP 200）：

```json
{
  "ok": true,
  "status": "ok",
  "message": "指令已发送成功",
  "command": "auto_conditioning_start",
  "target": {
    "vin": "LRWYGCFJ0MC201432",
    "vehicle_id": 1234567890123456,
    "id": 366766851154357,
    "display_name": "京AAS1530"
  },
  "result": {}
}
```

失败返回（HTTP 400/404）：

- 参数缺失 / JSON 类型错误
- 不支持的命令
- 车辆不在当前账号下
- Tesla API 返回的业务失败

---

## 4) OpenClaw 友好描述（机器可读）

- `GET /api/openclaw/describe`：轻量描述（端点、参数、示例）
- `GET /api/openclaw/openapi.json`：OpenAPI 3.0 schema

建议 OpenClaw 先拉取 `describe` 或 `openapi.json`，再进行工具调用配置。

---

## 5) 快速测试命令

```bash
curl -s "https://fleet-api.dev.xrunda.com/api/openclaw/vehicles" | jq .

curl -s -X POST "https://fleet-api.dev.xrunda.com/api/openclaw/command" \
  -H "Content-Type: application/json" \
  -d '{
    "command":"auto_conditioning_start",
    "vehicle_id":"366766851154357",
    "lang":"zh"
  }' | jq .
```

