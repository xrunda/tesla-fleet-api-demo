# Tesla Fleet API Demo 运行手册（中国区）

本文档基于当前项目代码整理，目标是让你从 0 到 1 稳定跑通：

- 能完成 Tesla OAuth 登录
- 能在首页看到车辆列表
- 能点进车辆详情页

---

## 1. 当前项目结构

核心文件：

- `tesla_oauth_demo.py`：Flask 主应用，负责 OAuth、拉车辆、页面展示。
- `get_partner_token.sh`：中国区 partner token 获取 + `partner_accounts` 注册脚本。
- `todo.md`：手工 curl 记录（可作为脚本等价参考）。
- `.well-known/appspecific/com.tesla.3p.public-key.pem`：Tesla 读取的公钥文件。
- `README.md`：原始演示文档。

推荐启动顺序：

1) 启动 Flask：`python tesla_oauth_demo.py`
2) 启动 ngrok：`ngrok http 8080`
3) 注册 partner：`bash get_partner_token.sh`
4) 浏览器打开 ngrok URL，执行登录流程

---

## 2. 代码配置项（中国区）

`tesla_oauth_demo.py` 顶部关键配置：

- `CLIENT_ID` / `CLIENT_SECRET`：来自 `developer.tesla.cn` 的应用
- `REDIRECT_URI`：`https://<你的-ngrok域名>/auth/callback`
- `FLEET_API_BASE`：`https://fleet-api.prd.cn.vn.cloud.tesla.cn`
- `AUTH_AUTHORIZE_BASE`：`https://auth.tesla.cn`
- `AUTH_TOKEN_URL`：`https://auth.tesla.cn/oauth2/v3/token`
- `SCOPES`：`openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds`

注意：

- `client_secret` 大小写必须 100% 一致（之前就出现过 1 个字符大小写导致 `unauthorized_client`）。
- `REDIRECT_URI` 必须与开发者后台完全一致（路径、协议、域名都一致）。

---

## 3. 启动前检查清单

### 3.1 ngrok 域名一致性

下面三处必须是同一个域名：

- Tesla 开发者后台的 Allowed Origin
- Tesla 开发者后台的 Redirect URI
- 代码里的 `REDIRECT_URI`

### 3.2 应用平台一致性

中国区必须是：

- 账号在 `tesla.cn`
- 应用在 `developer.tesla.cn`
- OAuth 与 token 端点使用 `auth.tesla.cn`
- Fleet API 使用 `fleet-api.prd.cn.vn.cloud.tesla.cn`

### 3.3 partner 注册

在登录前，先执行：

```bash
bash get_partner_token.sh
```

脚本会：

1. 通过 `client_credentials` 向 `auth.tesla.cn/oauth2/v3/token` 获取 partner token
2. 用该 token 调 `POST /api/1/partner_accounts` 注册 ngrok 域名

若此步未成功，后续即使 OAuth 成功，`/api/1/vehicles` 也可能无权限或返回空结果。

---

## 4. 应用启动流程（操作步骤）

### 步骤 A：启动 Flask

```bash
python tesla_oauth_demo.py
```

看到：`Running on http://127.0.0.1:8080` 即可。

### 步骤 B：启动 ngrok

```bash
ngrok http 8080
```

记下 Forwarding 的 https 域名。

### 步骤 C：注册 partner

```bash
bash get_partner_token.sh
```

预期：

- token 请求 200
- `partner_accounts` 请求 200

### 步骤 D：浏览器登录

打开：`https://<ngrok域名>`，点击 `Login with Tesla`。

预期：

- 跳到 `auth.tesla.cn`
- 授权后回调到 `/auth/callback`
- 自动回到首页并显示车辆列表

---

## 5. 代码执行链路（按请求）

### 5.1 `GET /`

在 `index()`：

- 若无 token：拼接 authorize URL，返回登录按钮
- 若有 token：
  - 拉 `/api/1/users/me`（补充用户信息）
  - 拉 `/api/1/vehicles`（展示车辆）
  - 页面显示当前配置、账号对比、车辆或调试信息

### 5.2 `GET /auth/callback`

在 `callback()`：

- 校验 `state`
- 用 `authorization_code` 向 `AUTH_TOKEN_URL` 换 token
- 请求体包含：`client_id`、`client_secret`、`code`、`redirect_uri`、`audience`
- 成功后保存 `tesla_api.tokens`，重定向回首页

### 5.3 `GET /vehicle/<id>`

在 `vehicle()`：

- 先查车辆状态
- 若不在线先 `wake_up`
- 再拉 `vehicle_data`
- 递归展开 JSON 渲染为 HTML 表格

---

## 6. 网络与错误处理（当前代码状态）

`TeslaAPI.api_get()` / `api_post()` 已做：

- `timeout=20`
- 捕获 `requests.exceptions.RequestException`
- 失败时记录 `last_network_error`，返回 `None`

首页调试输出会区分：

- 业务返回（有 HTTP 状态码）
- 网络/TLS异常（例如 `SSLEOFError`）

这样不会再直接白屏 500，而是能看到可读错误信息。

---

## 7. 常见问题与定位顺序

### 7.1 `Token Exchange Failed: unauthorized_client`

按顺序查：

1. `CLIENT_ID` / `CLIENT_SECRET` 是否来自同一个 `developer.tesla.cn` 应用
2. `client_secret` 大小写是否完全正确
3. `REDIRECT_URI` 是否与后台完全一致
4. Flask 是否已重启（是否加载了最新配置）

### 7.2 首页 500 或 “Internal Server Error”

先看 Flask 终端堆栈。若出现：

- `SSLEOFError`
- `Max retries exceeded`
- 指向 `fleet-api.prd.cn.vn.cloud.tesla.cn`

通常是本机网络/代理的 TLS 问题（不是 OAuth 参数问题）。

建议：

- 暂时关闭代理再试
- 或把 `*.tesla.cn` 走直连
- 避免 Fake-IP（198.18.x.x）劫持

### 7.3 登录成功但没有车辆

看首页底部调试行：

- 200 + `"response": []`：账号下无车辆或区域/账号不一致
- 401/403：token 或 partner 注册问题
- 网络异常：优先修网络/TLS

---

## 8. 一次性“最短跑通”命令清单

在项目根目录：

```bash
# 1) Flask
python tesla_oauth_demo.py

# 2) 另开终端：ngrok
ngrok http 8080

# 3) 再开终端：注册 partner
bash get_partner_token.sh
```

然后浏览器访问 ngrok 地址，点击登录，授权后应回到 `Your Vehicles` 并看到你的车。

---

## 9. 后续可优化项（可选）

- 将敏感配置改为环境变量（避免明文写在源码）
- 增加 `/health` 诊断路由（检查 auth/token/fleet 连通性）
- 增加结构化日志（区分 OAuth 失败、Fleet API 失败、网络失败）
- 补 requirements 文档，固定 `flask/requests` 版本
