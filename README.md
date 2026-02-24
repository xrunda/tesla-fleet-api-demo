# Tesla Fleet API Demo（中国区）

📹 **项目演示视频**

<video src="imgs/openclaw_tesla.mp4" controls width="600"></video>

这是一个基于 Flask 的 Tesla Fleet API 演示项目，已支持：

- OAuth 登录（中国区 `auth.tesla.cn`）
- 车辆列表与车辆详情可视化看板
- 中英文切换（`?lang=zh` / `?lang=en`）
- 车辆指令面板（全量命令入口）
- 可选 JSON 参数输入 + 一键填入示例
- Command Proxy 签名通道 + 自动 REST 回退（部分命令）
- OpenClaw 友好 API（无鉴权版）：车辆列表、命令执行、描述与 OpenAPI

![指令面板最新效果](imgs/ScreenShot_2026-02-24_101423_340.png)

---

## 1. 当前能力概览

### 数据看板

- 电池/续航/充电状态
- 驾驶状态（速度、档位、功率）
- 空调与温度
- 安全状态（锁车、哨兵、代客）
- 胎压、里程、软件版本、定位
- 原始数据折叠查看

### 指令面板

- 所有已接入命令均可点击执行
- 每条命令有中文描述（命令名保留英文）
- 高级参数区支持可选 JSON
- 一键填入示例参数，降低输入成本

---

## 2. 目录结构

- `tesla_oauth_demo.py`：主程序（OAuth、车辆数据、指令执行、UI）
- `get_partner_token.sh`：注册 partner domain 脚本
- `http_proxy/`：Docker 构建时在此目录写入编译好的 **Linux 版** tesla-http-proxy（仓库内不提交二进制）；本机需跑 proxy 时可用 `scripts/build_linux_proxy.sh` 生成 Linux 版，或从 [teslamotors/vehicle-command](https://github.com/teslamotors/vehicle-command) 自行编译
- `.well-known/appspecific/com.tesla.3p.public-key.pem`：对外公钥
- `private-key.pem` / `public-key.pem`：本地密钥
- `imgs/`：README 配图

---

## 3. 前置要求

1. 中国区 Tesla 账号（`tesla.cn`）
2. 在 `developer.tesla.cn` 创建应用并拿到：
   - `CLIENT_ID`
   - `CLIENT_SECRET`
3. （可选，本地联调）安装 `ngrok`
4. Python 3.10+
5. （指令签名推荐）`vehicle-command` proxy

---

## 4. 配置应用

可编辑 `tesla_oauth_demo.py` 顶部默认值，**更推荐**通过环境变量传入（见 4.1），便于 Docker/云部署且不写回仓库。

代码中读取的配置项：

- `CLIENT_ID` → 环境变量 `TESLA_CLIENT_ID`
- `CLIENT_SECRET` → 环境变量 `TESLA_CLIENT_SECRET`
- `REDIRECT_URI` → 环境变量 `TESLA_REDIRECT_URI`（必须与开发者后台一致）

中国区固定配置已内置：

- `FLEET_API_BASE = https://fleet-api.prd.cn.vn.cloud.tesla.cn`
- `AUTH_AUTHORIZE_BASE = https://auth.tesla.cn`
- `AUTH_TOKEN_URL = https://auth.tesla.cn/oauth2/v3/token`

### 4.1 由外部传入配置（环境变量与 PEM）

所有配置均可通过**环境变量**传入，无需修改代码，适合 Docker、K8s、Vercel 等部署方式。

| 环境变量 | 说明 |
|----------|------|
| `TESLA_CLIENT_ID` | 开发者后台 Client ID |
| `TESLA_CLIENT_SECRET` | 开发者后台 Client Secret |
| `TESLA_REDIRECT_URI` | 回调地址，需与开发者后台一致 |
| `FLASK_SECRET_KEY` | Session 签名密钥（生产必设） |
| `VEHICLE_COMMAND_PROXY_BASE` | 车辆指令签名代理地址（可选） |
| `VEHICLE_COMMAND_PROXY_INSECURE` | 是否跳过代理 TLS 校验，默认 `1`（可选） |
| `VEHICLE_COMMAND_PROXY_CA_CERT` | 代理 CA 证书路径（可选） |
| `SESSION_COOKIE_SECURE` | 是否仅 HTTPS 传输 Cookie，默认 `1`（可选） |

**公钥（`.well-known` 对外公钥）两种方式二选一：**

1. **文件方式**：在项目下放置 `.well-known/appspecific/com.tesla.3p.public-key.pem`（见第 5 节）。
2. **PEM 内容方式**：设置环境变量 `TESLA_PUBLIC_KEY_PEM`，值为公钥的**完整 PEM 文本**（含 `-----BEGIN PUBLIC KEY-----` 与 `-----END PUBLIC KEY-----`）。  
   适用于无法挂载文件的场景（如 Docker 仅用 env、K8s Secret 注入、Vercel 等），无需在镜像或运行时存在物理文件。

**Docker 示例：**

```bash
# 使用 -e 传入
docker run -p 8080:8080 \
  -e TESLA_CLIENT_ID=你的client_id \
  -e TESLA_CLIENT_SECRET=你的client_secret \
  -e TESLA_REDIRECT_URI=https://你的域名/auth/callback \
  -e FLASK_SECRET_KEY=随机强密钥 \
  -e "TESLA_PUBLIC_KEY_PEM=$(cat .well-known/appspecific/com.tesla.3p.public-key.pem)" \
  镜像名

# 或使用 env 文件（不要提交到 git）
docker run -p 8080:8080 --env-file .env 镜像名

# 若需指令签名：挂载 config 并映射 4443，容器内会先启动 proxy 再启动 Flask
docker run -p 4443:4443 -p 8080:8080 -v /你的路径/config:/app/config --env-file .env 镜像名
```

### 4.2 部署到 Kubernetes（K8s）

在 K8s 中提供 **fleet-key.pem** 有两种方式，任选其一即可让入口脚本启动 proxy：

**方式 A：Secret 挂载为 Volume**

将私钥存入 Secret，挂载到 `/app/config`，文件名须为 `fleet-key.pem`：

```yaml
# 将 fleet-key.pem 内容存入 Secret（替换为你的私钥）
kubectl create secret generic tesla-fleet-secret \
  --from-file=fleet-key.pem=/path/to/fleet-key.pem \
  --from-literal=TESLA_CLIENT_ID=xxx \
  --from-literal=TESLA_CLIENT_SECRET=xxx \
  --from-literal=FLASK_SECRET_KEY=xxx \
  --from-literal=TESLA_REDIRECT_URI=https://你的域名/auth/callback
```

在 Deployment 中挂载并暴露 8080（及可选 4443）：

```yaml
volumeMounts:
  - name: config
    mountPath: /app/config
    readOnly: true
volumes:
  - name: config
    secret:
      secretName: tesla-fleet-secret
      items:
        - key: fleet-key.pem
          path: fleet-key.pem
```

**方式 B：Secret 通过环境变量注入（FLEET_KEY_PEM）**

私钥内容通过环境变量传入，入口脚本会写入临时文件并启动 proxy（适合不想挂载 Volume 时）：

```yaml
env:
  - name: FLEET_KEY_PEM
    valueFrom:
      secretKeyRef:
        name: tesla-fleet-secret
        key: fleet-key.pem
  - name: TESLA_CLIENT_ID
    valueFrom:
      secretKeyRef:
        name: tesla-fleet-secret
        key: TESLA_CLIENT_ID
  # ... 其他 TESLA_*、FLASK_SECRET_KEY 等
```

创建 Secret 时把私钥整段内容放入某 key（如 `fleet-key.pem`），value 为 PEM 文本（含 `-----BEGIN EC PRIVATE KEY-----` 等）。同一 Pod 内 proxy 与 Flask 同机，`VEHICLE_COMMAND_PROXY_BASE` 可不设（默认 `https://127.0.0.1:4443`）；对外 HTTPS 由 Ingress 提供即可。

**说明**：`private-key.pem` / `public-key.pem` 仅用于本地生成与拷贝到 `.well-known`；Flask 应用只负责对外提供公钥（文件或 `TESLA_PUBLIC_KEY_PEM`）。车辆指令签名使用的私钥由独立进程 `tesla-http-proxy` 管理，需在其自己的配置中传入对应 key 文件或内容。

---

## 5. 生成并发布公钥

```bash
cd "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo"

openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
openssl ec -in private-key.pem -pubout -out public-key.pem
mkdir -p .well-known/appspecific
cp public-key.pem .well-known/appspecific/com.tesla.3p.public-key.pem
```

---

## 6. 启动服务（基础数据能力）

### 6.1 启动 Flask

```bash
cd "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo"
python tesla_oauth_demo.py
```

### 6.2 启动 ngrok（仅本地开发需要）

```bash
ngrok http 8080
```

把 ngrok 域名填回（仅本地调试时需要）：

- Tesla 开发者后台 `Allowed Origin` / `Redirect URI`
- 代码中的 `REDIRECT_URI`

### 6.3 注册 partner domain

```bash
cd "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo"
bash get_partner_token.sh
```

---

## 7. 指令签名（推荐）

对于大量新车型，车辆指令需要 Tesla Vehicle Command Protocol 签名。  
建议启动 `tesla-http-proxy` 后再执行命令。

**Docker 用户**：镜像内已包含 Linux 版 proxy；**启动顺序与 README 一致：先 proxy，再 HTTP 服务**。入口脚本会检测 `/app/config` 下是否有 **`fleet-key.pem`**（车辆指令签名私钥，必选）；若还有 `tls-key.pem`、`tls-cert.pem` 则使用，**否则自动生成自签名 TLS 证书**（适用于由 Ingress 提供对外 HTTPS、仅需后端跑 proxy 的场景，此时不必准备 proxy 的 PEM）。例如：

```bash
# 仅挂载 fleet-key.pem（TLS 自动生成）
docker run -p 4443:4443 -p 8080:8080 -v /你的路径/config:/app/config --env-file .env 镜像名
```

### 7.1 启动 proxy（示例，非 Docker）

```bash
~/go/bin/tesla-http-proxy \
  -tls-key "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo/config/tls-key.pem" \
  -cert "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo/config/tls-cert.pem" \
  -key-file "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo/config/fleet-key.pem" \
  -host 127.0.0.1 \
  -port 4443
```

### 7.2 启动 Flask（连接 proxy，非 Docker）

```bash
cd "/Users/liguang/Documents/xRunda/project/AI/github/tesla-fleet-api-demo"
export VEHICLE_COMMAND_PROXY_BASE="https://127.0.0.1:4443"
export VEHICLE_COMMAND_PROXY_INSECURE="1"
python tesla_oauth_demo.py
```

---

## 8. 页面入口

- 本地开发：
  - 首页：`https://<你的-ngrok-domain>`
  - 回调：`https://<你的-ngrok-domain>/auth/callback`
- 生产环境：
  - 首页：`https://<你的正式域名>`（例如 `https://fleet-api.dev.xrunda.com`）
  - 回调：`https://<你的正式域名>/auth/callback`
- 车辆详情：点击列表中的车辆进入看板与指令面板
- 语言切换：
  - 中文：`?lang=zh`
  - 英文：`?lang=en`

---

## 9. OpenClaw 集成 API（无鉴权版）

当前已提供最简 API，便于 OpenClaw 机器人直接调用：

- `GET /api/health`
- `GET /api/openclaw/vehicles`
- `POST /api/openclaw/command`
- `GET /api/openclaw/describe`
- `GET /api/openclaw/openapi.json`

详细说明见：`OPENCLAW_API.md`

---

## 10. 常见问题

### `Vehicle Command Protocol required`

- 含义：车辆要求签名命令
- 处理：启动 `vehicle-command` proxy，并设置 `VEHICLE_COMMAND_PROXY_BASE`

### `command requires using the REST API`

- 含义：该命令应走 REST API
- 当前代码：已支持自动回退尝试

### `JSON 参数格式错误，请检查 payload`

- 含义：高级参数里的 JSON 不合法
- 建议：先点“一键填入”再改字段

---

## 11. 配图

开发者后台配置示例：

![Credentials & APIs](imgs/credentials_and_apis.png)
![API Scopes](imgs/api_and_scopes.png)

当前项目 UI 示例：

![Dashboard](imgs/ScreenShot_2026-02-24_101423_340.png)
![Commands](imgs/ScreenShot_2026-02-24_101447_480.png)
![Latest Commands Panel](imgs/ScreenShot_2026-02-24_101852_000.png)
