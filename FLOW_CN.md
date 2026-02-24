# Tesla Fleet API 项目流程说明（中国区）

按「文档 + 代码」顺序说明每一步在做什么、对应哪段代码，以及中国区要注意的点。做完所有步骤后，最终页面应能显示你的车辆列表。

---

## 一、整体流程概览

```
[1] 生成密钥对 → [2] 安装并启动 ngrok → [3] 在 developer.tesla.cn 创建应用
       ↓                    ↓                              ↓
[4] 配置并启动 Python 应用 ← 用 ngrok 域名填到应用与代码里
       ↓
[5] 用「合作伙伴令牌」把 ngrok 域名注册到中国区 Fleet API（partner_accounts）
       ↓
[6] 用户访问 ngrok 地址 → 点「Login with Tesla」→ 授权 → 回调拿到 token
       ↓
[7] 用 token 调 GET /api/1/vehicles → 页面显示车辆列表 → 点某车可看详情
```

**中国区要点**：账号/应用在 **developer.tesla.cn**，授权与 token 用 **auth.tesla.cn**，Fleet API 用 **fleet-api.prd.cn.vn.cloud.tesla.cn**。下面每步会标出对应代码/脚本。

---

## 二、步骤 1：生成公钥/私钥（README Step 1）

**文档**：README「Generate a Public/Private Key Pair」

**作用**：后续「在车上安装密钥」发指令时，Tesla 用你提供的公钥验证请求；本地用私钥签名。当前 demo 主要做「查车辆数据」，本步不做也能看到车辆列表；若要发指令（如开空调），需要完成本步并在车里安装公钥。

**操作**（在项目根目录执行）：

```bash
openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
openssl ec -in private-key.pem -pubout -out public-key.pem
mkdir -p .well-known/appspecific
cp public-key.pem .well-known/appspecific/com.tesla.3p.public-key.pem
```

**代码对应**：Flask 里有一条路由，把公钥提供给 Tesla 拉取：

- `tesla_oauth_demo.py` 第 281–284 行：`@app.route('/.well-known/appspecific/<path:filename>')`，用 `send_from_directory('.well-known/appspecific', filename)` 提供 `com.tesla.3p.public-key.pem`。Tesla 会请求 `https://你的域名/.well-known/appspecific/com.tesla.3p.public-key.pem` 来验证你的应用。

---

## 三、步骤 2：安装并启动 ngrok（README Step 2）

**文档**：README「Install NGROK」

**作用**：让外网通过 HTTPS 访问你本机的 8080 端口。Tesla 回调、partner 注册、公钥拉取都必须是「可被 Tesla 访问的固定域名」，本地 localhost 不行，所以用 ngrok 临时提供一个。

**操作**：

1. 安装：`brew install ngrok`（或从 ngrok.com 下载），并配置 authtoken。
2. 启动隧道：`ngrok http 8080`。
3. 记下转发域名，例如：`https://unrebuffable-antonietta-monocled.ngrok-free.dev`（你当前用的）。

**代码对应**：

- `REDIRECT_URI`、Allowed Origin、Redirect URI、partner 的 `domain` 都必须等于这个 ngrok 域名（不要带路径，callback 路径在 REDIRECT_URI 里单独写）。
- `tesla_oauth_demo.py` 第 10 行：`REDIRECT_URI = "https://unrebuffable-antonietta-monocled.ngrok-free.dev/auth/callback"`。
- `get_partner_token.sh` 里 `domain` 也必须是同一个域名。

---

## 四、步骤 3：在 Tesla 开发者平台创建应用（中国区）

**文档**：README「Create a new Tesla Fleet API Application」；中国区要用 **developer.tesla.cn**，不是 developer.tesla.com。

**作用**：拿到 `client_id` 和 `client_secret`，并让 Tesla 允许「你的 ngrok 域名 + 回调地址」做 OAuth。

**操作**（在 developer.tesla.cn）：

1. 登录：https://developer.tesla.cn ，使用 tesla.cn 账号（如 317423621@qq.com）。
2. 创建应用（你已有 openclaw）：
   - **Allowed Origin(s)**：`https://unrebuffable-antonietta-monocled.ngrok-free.dev`
   - **Redirect URI**：`https://unrebuffable-antonietta-monocled.ngrok-free.dev/auth/callback`
   - **OAuth 授权类型**：勾选 `authorization-code` 和 `client_credentials`（前者给用户登录，后者给下面「合作伙伴注册」用）。
   - **API/Scopes**：勾选车辆相关（如 vehicle_device_data、vehicle_cmds、vehicle_charging_cmds 等，按页面选项）。
3. 保存后复制 **客户端 ID** 和 **客户端密钥**。

**代码对应**：

- `tesla_oauth_demo.py` 第 8–10 行：`CLIENT_ID`、`CLIENT_SECRET`、`REDIRECT_URI` 必须与开发者后台完全一致（含大小写、尾部斜杠等）。
- `get_partner_token.sh` 和 `todo.md` 里的 `CLIENT_ID`/`CLIENT_SECRET` 也应与开发者后台一致（中国区用 HKIN 大写 I 的 secret）。

---

## 五、步骤 4：配置并启动 Python 应用（README “Run Our Example Python Web Application”）

**文档**：README「Replace the following values」+ 启动命令。

**作用**：提供网页「Login with Tesla」、接收 Tesla 回调、用 code 换 token、用 token 调 Fleet API 拉车辆列表并展示。

**操作**：

1. 确认代码里中国区配置（你项目里已改好）：
   - `FLEET_API_BASE` = 中国区
   - `AUTH_AUTHORIZE_BASE` = auth.tesla.cn
   - `AUTH_TOKEN_URL` = auth.tesla.cn/oauth2/v3/token
   - `CLIENT_ID` / `CLIENT_SECRET` = developer.tesla.cn 的 openclaw
2. 启动：在项目根目录执行 `python tesla_oauth_demo.py`，看到 `Running on http://127.0.0.1:8080`。
3. 保持 ngrok 在另一个终端运行，浏览器访问：`https://unrebuffable-antonietta-monocled.ngrok-free.dev`。

**代码流程简述**：

| 用户操作 / 请求 | 代码位置 | 行为 |
|----------------|----------|------|
| 访问 `/` 且尚未登录 | `index()` 第 102–110 行 | 没有 `tesla_api.tokens` 时，拼出 `AUTH_AUTHORIZE_BASE/oauth2/v3/authorize?...`，返回「Login with Tesla」链接。 |
| 点击链接 | 浏览器跳转 | 跳到 auth.tesla.cn，用户登录并授权，Tesla 重定向到 `REDIRECT_URI?code=xxx&state=xxx`。 |
| 请求 `/auth/callback?code=...&state=...` | `callback()` 第 173–214 行 | 校验 `state`，用 `code` 向 `AUTH_TOKEN_URL` 发 POST（grant_type=authorization_code, audience=FLEET_API_BASE），拿到 access_token/refresh_token；写入 `tesla_api.tokens`，再 redirect 到 `/`。 |
| 再次访问 `/`（已登录） | `index()` 第 111–171 行 | 用 `tesla_api.get_vehicles()` 调 `GET {FLEET_API_BASE}/api/1/vehicles`；若车辆列表为空会再调 `get_vehicles_response()` 并在页面显示调试信息（状态码、响应摘要）。 |
| 点击某辆车 `/vehicle/<id>` | `vehicle(vid)` 第 216–279 行 | 先查状态，若未 online 则调 wake_up 并轮询；再 `GET .../vehicles/{id}/vehicle_data`，把返回展成表格。 |

**为何必须做步骤 5（partner 注册）**：Fleet API 要求你的「域名」先通过 partner_accounts 注册到该区域，否则即使用户 OAuth 成功，调 `GET /api/1/vehicles` 也可能 403 或返回空。中国区要在「中国区 Fleet API」上注册该域名。

---

## 六、步骤 5：用合作伙伴令牌注册域名（README “Register with partner” / 中国区）

**文档**：README 里「Step 4: Register with partner」；中国区要用 **auth.tesla.cn** 取 token，且 **AUDIENCE** 为中国区 Fleet API。

**作用**：向中国区 Fleet API 声明「这个 ngrok 域名是我的合作伙伴应用」，这样该域名下发起的用户 token 才能正常调 `GET /api/1/vehicles` 等接口。

**操作**（二选一）：

**方式 A：脚本（推荐）**

```bash
bash get_partner_token.sh
```

脚本会：

1. 用 `CLIENT_ID` + `CLIENT_SECRET` 向 `https://auth.tesla.cn/oauth2/v3/token` 发 `grant_type=client_credentials`，并带 `audience=https://fleet-api.prd.cn.vn.cloud.tesla.cn`，拿到 partner 用的 access_token。
2. 用该 token 调 `POST https://fleet-api.prd.cn.vn.cloud.tesla.cn/api/1/partner_accounts`，body 为 `{"domain": "unrebuffable-antonietta-monocled.ngrok-free.dev"}`。

**方式 B：按 todo.md 里命令整段复制到终端执行**（先取 token，再 curl partner_accounts，保证 `ACCESS_TOKEN` 来自中国区 auth.tesla.cn 且 audience 为中国区）。

**代码/脚本对应**：

- `get_partner_token.sh`：第 12–18 行请求 token；第 37–41 行请求 partner_accounts。中国区使用 `TOKEN_URL='https://auth.tesla.cn/oauth2/v3/token'` 和 `AUDIENCE='https://fleet-api.prd.cn.vn.cloud.tesla.cn'`。
- 若未执行本步或域名填错，前端 OAuth 正常也可能出现「车辆列表为空」或接口 403。

---

## 七、步骤 6：用户登录并看到车辆列表（完整 OAuth + API 流程）

**顺序**：先完成步骤 1–5，再在浏览器访问 ngrok 地址。

1. **打开首页**  
   `https://unrebuffable-antonietta-monocled.ngrok-free.dev`  
   → 代码走 `index()`，因无 token 返回「Login with Tesla」链接（指向 auth.tesla.cn）。

2. **点击登录**  
   → 跳转 auth.tesla.cn，用 tesla.cn 账号登录并授权。

3. **回调**  
   → Tesla 重定向到 `https://...ngrok-free.dev/auth/callback?code=xxx&state=xxx`  
   → `callback()` 用 code 向 `AUTH_TOKEN_URL`（auth.tesla.cn）换 token，并带 `audience=FLEET_API_BASE`（中国区），写入 `tesla_api.tokens`，再重定向回 `/`。

4. **再次进入首页**  
   → `index()` 发现已有 token，调用 `get_vehicles()` → `GET {FLEET_API_BASE}/api/1/vehicles`。  
   → 若 partner 已注册且账号下有车，应返回车辆数组；页面渲染成「Your Vehicles」+ 车辆链接。  
   → 若仍为空，页面会显示「当前接口配置（中国区）」和「车辆列表为空」的调试信息（状态码与响应摘要），便于排查。

5. **点击某辆车**  
   → 进入 `/vehicle/<id>`，代码先查状态，必要时 wake_up，再拉取 `vehicle_data` 并展示为表格。

---

## 八、中国区配置与代码对照表

| 配置项 | 中国区值 | 代码位置 |
|--------|----------|----------|
| Fleet API 基地址 | `https://fleet-api.prd.cn.vn.cloud.tesla.cn` | `tesla_oauth_demo.py`：FLEET_API_BASE；api_get/api_post 的 base |
| 授权页 | `https://auth.tesla.cn/oauth2/v3/authorize` | AUTH_AUTHORIZE_BASE + `/oauth2/v3/authorize` |
| Token 交换 / Refresh | `https://auth.tesla.cn/oauth2/v3/token` | AUTH_TOKEN_URL；callback 与 refresh() |
| 应用与密钥 | developer.tesla.cn 的 openclaw | CLIENT_ID / CLIENT_SECRET |
| Token 请求体 | 必须带 `audience=FLEET_API_BASE` | callback 与 refresh() 的 data["audience"] |
| Partner 注册 | 同上 token URL，audience 为中国区；partner_accounts 用中国区 base | get_partner_token.sh / todo.md |

---

## 九、若最终界面仍看不到车：自检清单

1. **Partner 是否注册成功**  
   运行过 `bash get_partner_token.sh` 且返回 200？域名是否与 REDIRECT_URI 的域名一致（无尾斜杠、无 /auth/callback）？

2. **登录是否走中国区**  
   点击「Login with Tesla」后，浏览器地址栏是否是 auth.tesla.cn？若仍是 auth.tesla.com，说明 AUTH_AUTHORIZE_BASE 未生效或用了国际应用 client_id。

3. **Token 是否中国区**  
   callback 是否成功（未出现 Token Exchange Failed）？若成功，页面「当前接口配置」里 AUTH_TOKEN_URL 应为 auth.tesla.cn，audience 应为 fleet-api.prd.cn.vn.cloud.tesla.cn。

4. **车辆接口返回**  
   若列表为空，看页面上的「车辆列表为空。接口 GET /api/1/vehicles 状态码: xxx；响应摘要: ...」：  
   - 200 + `"response":[]`：账号在该区域下暂无车辆或车辆未关联到该账号。  
   - 401/403：token 或 partner 域名有问题，对照上面配置再查。

5. **应用与密钥**  
   developer.tesla.cn 里 openclaw 的 Redirect URI、Allowed Origin 是否与代码里完全一致？客户端密钥是否与代码里一致（如 HKIN 大写 I）？

按上述顺序做完并逐项核对，最终界面应能显示你的车；若某一步报错，把该步的报错信息或页面上的调试摘要贴出来即可继续排查。
