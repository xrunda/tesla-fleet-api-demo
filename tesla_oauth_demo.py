
from flask import Flask, redirect, request, send_from_directory
import secrets, requests, urllib.parse, time, os, base64, json

app = Flask(__name__)

# 中国区应用（developer.tesla.cn 的 openclaw），与 auth.tesla.cn 一致才不会被报 client_id 无法识别
CLIENT_ID = "29357fd6-434e-4d3b-a305-bb63a65d9f55"
CLIENT_SECRET = "ta-secret.syUH05HKiN++h+xN"
REDIRECT_URI = "https://unrebuffable-antonietta-monocled.ngrok-free.dev/auth/callback"
SCOPES = "openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds"
STATE = secrets.token_urlsafe(32)

# 中国区配置（参见官方 Regions and Countries / Third-Party Tokens 文档）
# https://developer.tesla.com/docs/fleet-api/getting-started/regions-countries
# https://developer.tesla.com/docs/fleet-api/authentication/third-party-tokens
FLEET_API_BASE = "https://fleet-api.prd.cn.vn.cloud.tesla.cn"
# 中国区用户需走 auth.tesla.cn 授权与 token 交换，否则会报 unauthorized_client / unsupported issuer
AUTH_AUTHORIZE_BASE = "https://auth.tesla.cn"
AUTH_TOKEN_URL = "https://auth.tesla.cn/oauth2/v3/token"

# 用于页面显示「是否与预期账号一致」（与 todo.md 中一致即可）
EXPECTED_EMAIL = "317423621@qq.com"

class TeslaAPI:
    def __init__(self, client_id, client_secret, redirect_uri, scopes):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.tokens = {}
        self.state = STATE
        self.user_info = {}
        self.last_network_error = ""

    def valid(self):
        return self.tokens and (int(time.time()) - self.tokens["obtained_at"] < self.tokens["expires_in"] - 60)

    def refresh(self):
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.tokens["refresh_token"],
        }
        # 中国区 token 需带 audience，否则新 access_token 会报 unsupported issuer
        data["audience"] = FLEET_API_BASE
        r = requests.post(AUTH_TOKEN_URL, data=data).json()
        r["obtained_at"] = int(time.time())
        self.tokens.update(r)

    def api_get(self, path):
        if not self.valid():
            self.refresh()
        try:
            return requests.get(
                f"{FLEET_API_BASE}{path}",
                headers={"Authorization": f"Bearer {self.tokens['access_token']}"},
                timeout=20,
            )
        except requests.exceptions.RequestException as e:
            self.last_network_error = str(e)
            return None

    def api_post(self, path):
        if not self.valid():
            self.refresh()
        try:
            return requests.post(
                f"{FLEET_API_BASE}{path}",
                headers={"Authorization": f"Bearer {self.tokens['access_token']}"},
                timeout=20,
            )
        except requests.exceptions.RequestException as e:
            self.last_network_error = str(e)
            return None

    def get_vehicles(self):
        resp = self.api_get("/api/1/vehicles")
        if resp is None:
            return []
        try:
            return resp.json().get('response', [])
        except Exception:
            return []

    def get_vehicles_response(self):
        """返回原始 response，便于在车辆为空时查看状态码和响应体"""
        return self.api_get("/api/1/vehicles")

    def get_user_me(self):
        """Fleet API: 当前用户账号摘要，可能包含 email 等"""
        try:
            resp = self.api_get("/api/1/users/me")
            if resp is None:
                return {}
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception:
            return {}

    def get_vehicle_state(self, vid):
        vehicles = self.get_vehicles()
        vehicle = next((v for v in vehicles if str(v.get('id')) == str(vid)), None)
        return vehicle.get('state') if vehicle else None

    def wake_up_vehicle(self, vid):
        return self.api_post(f"/api/1/vehicles/{vid}/wake_up")

    def get_vehicle_data(self, vid):
        return self.api_get(f"/api/1/vehicles/{vid}/vehicle_data")

tesla_api = TeslaAPI(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPES)

@app.route("/")
def index():
    if not tesla_api.tokens:
        url = f"{AUTH_AUTHORIZE_BASE}/oauth2/v3/authorize?" + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "state": tesla_api.state
        })
        return f"<h1>Tesla Fleet</h1><a href='{url}'>Login with Tesla</a>"
    # 若 id_token 里没有 email，用 Fleet API /users/me 补全
    user = getattr(tesla_api, "user_info", {}) or {}
    if not user.get("email") and not user.get("email_address"):
        me = tesla_api.get_user_me()
        if me:
            # Fleet API 可能返回 {"response": {...}} 或直接 {...}
            me_data = me.get("response", me) if isinstance(me.get("response"), dict) else me
            user = {**user, **me_data}
            tesla_api.user_info = user

    cars = tesla_api.get_vehicles()
    # 账号展示：优先邮箱，其次 name/sub
    display_parts = []
    name = user.get("name") or user.get("preferred_username")
    email = user.get("email") or user.get("email_address") or ""
    subject = user.get("sub", "")
    if name:
        display_parts.append(name)
    if email:
        display_parts.append(email)
    if not display_parts and subject:
        display_parts.append(subject)
    current_display = " / ".join(display_parts) if display_parts else subject or "—"
    is_same = "是" if email and email.strip().lower() == EXPECTED_EMAIL.strip().lower() else "否"
    account_line = (
        f"<p><b>预期账号:</b> {EXPECTED_EMAIL} &nbsp;|&nbsp; "
        f"<b>当前登录:</b> {current_display} &nbsp;|&nbsp; "
        f"<b>是否一致:</b> {is_same}</p>"
    )

    # 页面上打印当前中国区配置与请求信息，便于核对
    config_pre = (
        "<details><summary><b>当前接口配置（中国区）</b></summary><pre style='background:#f0f0f0;padding:12px;font-size:12px;overflow:auto;'>"
        f"区域: 中国区 (CN)\n"
        f"FLEET_API_BASE = {FLEET_API_BASE}\n"
        f"AUTH_AUTHORIZE_BASE = {AUTH_AUTHORIZE_BASE}\n"
        f"AUTH_TOKEN_URL = {AUTH_TOKEN_URL}\n"
        f"REDIRECT_URI = {REDIRECT_URI}\n"
        f"CLIENT_ID = {CLIENT_ID[:8]}...{CLIENT_ID[-4:] if len(CLIENT_ID) > 12 else CLIENT_ID}\n"
        f"Token 交换 / Refresh 使用 audience = {FLEET_API_BASE}\n"
        f"GET 车辆列表实际请求 URL = {FLEET_API_BASE}/api/1/vehicles\n"
        f"GET 用户信息实际请求 URL = {FLEET_API_BASE}/api/1/users/me"
        "</pre></details>"
    )

    vehicles_html = "".join(
        f"<p><a href='/vehicle/{c['id']}'>{c['display_name']} ({c['vin']})</a></p>"
        for c in cars
    )
    # 车辆为空时显示接口返回，便于排查
    debug_html = ""
    if not cars:
        v_resp = tesla_api.get_vehicles_response()
        if v_resp is None:
            debug_html = (
                f"<p style='color:#b00020;font-size:14px;'>"
                f"请求中国区 Fleet API 失败（网络/TLS 异常）："
                f"<code>{tesla_api.last_network_error or '(未知错误)'}</code></p>"
            )
        else:
            debug_html = (
                f"<p style='color:#666;font-size:14px;'>"
                f"车辆列表为空。接口 GET /api/1/vehicles 状态码: {v_resp.status_code}；"
                f"响应摘要: <code>{v_resp.text[:500] if v_resp.text else '(无内容)'}</code></p>"
            )

    return "<h1>Your Vehicles</h1>" + account_line + config_pre + vehicles_html + debug_html

@app.route("/auth/callback", strict_slashes=False)
# @app.route("/auth/callback/", strict_slashes=False)
def callback():
    if "error" in request.args:
        return f"<h1>Tesla OAuth Error</h1><pre>{dict(request.args)}</pre>", 400

    # Validate state parameter
    state = request.args.get("state")
    if state != tesla_api.state:
        return "<h1>Invalid state parameter (possible CSRF)</h1>", 400

    code = request.args.get("code")
    if not code:
        return f"<pre>{dict(request.args)}</pre>", 400

    # audience 必填，且必须为当前区域的 Fleet API base URL，否则中国区会返回 unsupported issuer
    resp = requests.post(AUTH_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "audience": FLEET_API_BASE,
    })
    if resp.status_code != 200:
        return f"<h1>Token Exchange Failed</h1><pre>{resp.text}</pre>", 400
    token = resp.json()
    token["obtained_at"] = int(time.time())
    tesla_api.tokens.update(token)
    # Decode id_token (if present) to capture basic account info for display
    id_token = token.get("id_token")
    if id_token:
        parts = id_token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            padding = "=" * (-len(payload) % 4)
            try:
                decoded_bytes = base64.urlsafe_b64decode(payload + padding)
                tesla_api.user_info = json.loads(decoded_bytes.decode("utf-8"))
            except Exception:
                tesla_api.user_info = {}
    return redirect("/")

@app.route("/vehicle/<vid>")
def vehicle(vid):
    import time
    # 1. Get vehicle state (without waking up)
    state = tesla_api.get_vehicle_state(vid)
    if state is None:
        return f"<h2>Vehicle not found in account.</h2>", 404
    # 2. If not online, try to wake up
    if state != 'online':
        wake_resp = tesla_api.wake_up_vehicle(vid)
        if wake_resp is None:
            return f"<h2>网络/TLS 异常（wake_up）：</h2><pre>{tesla_api.last_network_error}</pre>", 502
        try:
            wake_data = wake_resp.json()
        except Exception as e:
            return f"<h2>Wake up command failed (non-JSON response):</h2><pre>{wake_resp.text}</pre>", 500
        # 3. Poll for 'online' state, up to 5 times
        for attempt in range(5):
            time.sleep(2)
            poll_state = tesla_api.get_vehicle_state(vid)
            if poll_state == 'online':
                break
        else:
            return f"<h2>Vehicle did not wake up after several attempts.</h2><pre>{wake_data}</pre>", 500
    # 4. Fetch vehicle data
    data_resp = tesla_api.get_vehicle_data(vid)
    if data_resp is None:
        return f"<h2>网络/TLS 异常（vehicle_data）：</h2><pre>{tesla_api.last_network_error}</pre>", 502
    try:
        data = data_resp.json()
    except Exception as e:
        return f"<h2>Error parsing vehicle data response:</h2><pre>{data_resp.text}</pre>", 500

    # Pretty-print: flatten top-level keys and show as HTML table
    def render_dict(d, parent_key=""):
        rows = []
        for k, v in d.items():
            key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                rows.extend(render_dict(v, key))
            else:
                rows.append(f"<tr><td>{key}</td><td>{v}</td></tr>")
        return rows

    vehicle_info = data.get('response', {})
    table_rows = render_dict(vehicle_info)
    html = f'''
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f8f8f8; }}
        table {{ border-collapse: collapse; width: 80%; margin: 2em auto; background: #fff; }}
        th, td {{ border: 1px solid #ccc; padding: 8px 12px; }}
        th {{ background: #eee; }}
        tr:nth-child(even) {{ background: #f2f2f2; }}
        h2 {{ text-align: center; }}
    </style>
    </head>
    <body>
    <h2>Vehicle Data</h2>
    <table>
        <tr><th>Field</th><th>Value</th></tr>
        {''.join(table_rows)}
    </table>
    </body>
    </html>
    '''
    return html


@app.route('/.well-known/appspecific/<path:filename>')
def well_known(filename):
    return send_from_directory('.well-known/appspecific', filename)

app.run(port=8080, debug=False)
