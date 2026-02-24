
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
    lang = (request.args.get("lang") or "zh").lower()
    if lang not in ("zh", "en"):
        lang = "zh"
    tt = {
        "zh": {
            "title": "我的车辆",
            "login": "使用 Tesla 登录",
            "expected": "预期账号",
            "current": "当前登录",
            "matched": "是否一致",
            "yes": "是",
            "no": "否",
            "config": "当前接口配置（中国区）",
            "empty": "车辆列表为空。",
            "network": "请求中国区 Fleet API 失败（网络/TLS 异常）：",
            "view": "查看仪表盘",
            "lang": "语言",
        },
        "en": {
            "title": "My Vehicles",
            "login": "Login with Tesla",
            "expected": "Expected Account",
            "current": "Current Login",
            "matched": "Matched",
            "yes": "Yes",
            "no": "No",
            "config": "Current API Config (China)",
            "empty": "No vehicles found.",
            "network": "China Fleet API request failed (network/TLS):",
            "view": "Open Dashboard",
            "lang": "Language",
        },
    }[lang]

    if not tesla_api.tokens:
        url = f"{AUTH_AUTHORIZE_BASE}/oauth2/v3/authorize?" + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "state": tesla_api.state
        })
        return (
            "<h1>Tesla Fleet</h1>"
            f"<p><b>{tt['lang']}:</b> <a href='/?lang=zh'>中文</a> | <a href='/?lang=en'>English</a></p>"
            f"<a href='{url}'>{tt['login']}</a>"
        )
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
    is_same = tt["yes"] if email and email.strip().lower() == EXPECTED_EMAIL.strip().lower() else tt["no"]
    account_line = (
        f"<p><b>{tt['expected']}:</b> {EXPECTED_EMAIL} &nbsp;|&nbsp; "
        f"<b>{tt['current']}:</b> {current_display} &nbsp;|&nbsp; "
        f"<b>{tt['matched']}:</b> {is_same}</p>"
    )

    # 页面上打印当前中国区配置与请求信息，便于核对
    config_pre = (
        f"<details><summary><b>{tt['config']}</b></summary><pre style='background:#f0f0f0;padding:12px;font-size:12px;overflow:auto;'>"
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
        f"<p><a href='/vehicle/{c['id']}?lang={lang}'>{c['display_name']} ({c['vin']})</a> - {tt['view']}</p>"
        for c in cars
    )
    # 车辆为空时显示接口返回，便于排查
    debug_html = ""
    if not cars:
        v_resp = tesla_api.get_vehicles_response()
        if v_resp is None:
            debug_html = (
                f"<p style='color:#b00020;font-size:14px;'>"
                f"{tt['network']}"
                f"<code>{tesla_api.last_network_error or '(未知错误)'}</code></p>"
            )
        else:
            debug_html = (
                f"<p style='color:#666;font-size:14px;'>"
                f"{tt['empty']} GET /api/1/vehicles status: {v_resp.status_code}; "
                f"响应摘要: <code>{v_resp.text[:500] if v_resp.text else '(无内容)'}</code></p>"
            )

    lang_html = f"<p><b>{tt['lang']}:</b> <a href='/?lang=zh'>中文</a> | <a href='/?lang=en'>English</a></p>"
    return f"<h1>{tt['title']}</h1>" + lang_html + account_line + config_pre + vehicles_html + debug_html

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

    lang = (request.args.get("lang") or "zh").lower()
    if lang not in ("zh", "en"):
        lang = "zh"

    i18n = {
        "zh": {
            "dashboard": "车辆仪表盘",
            "back": "返回车辆列表",
            "battery": "电池与续航",
            "driving": "驾驶状态",
            "climate": "空调与温度",
            "security": "安全状态",
            "charging": "充电明细",
            "location": "车辆定位",
            "software": "软件与系统",
            "tires": "胎压监测",
            "raw": "查看原始数据",
            "updated": "更新时间",
            "online": "在线",
            "offline": "离线",
            "charging_on": "充电中",
            "charging_off": "未充电",
            "parked": "已停车",
            "moving": "行驶中",
            "locked": "已锁车",
            "unlocked": "未锁车",
            "all_closed": "车门与前后备厢已关闭",
            "open_detected": "检测到开门/开厢",
            "yes": "是",
            "no": "否",
            "unknown": "未知",
            "map": "在地图中打开",
            "lang": "语言",
        },
        "en": {
            "dashboard": "Vehicle Dashboard",
            "back": "Back to Vehicles",
            "battery": "Battery & Range",
            "driving": "Driving Status",
            "climate": "Climate",
            "security": "Security",
            "charging": "Charging Details",
            "location": "Location",
            "software": "Software & System",
            "tires": "Tire Pressure",
            "raw": "View Raw Data",
            "updated": "Updated",
            "online": "Online",
            "offline": "Offline",
            "charging_on": "Charging",
            "charging_off": "Not Charging",
            "parked": "Parked",
            "moving": "Moving",
            "locked": "Locked",
            "unlocked": "Unlocked",
            "all_closed": "All doors and trunks closed",
            "open_detected": "Door/trunk open detected",
            "yes": "Yes",
            "no": "No",
            "unknown": "Unknown",
            "map": "Open in Maps",
            "lang": "Language",
        },
    }[lang]

    def render_dict(d, parent_key=""):
        rows = []
        for k, v in d.items():
            key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                rows.extend(render_dict(v, key))
            else:
                rows.append(f"<tr><td>{key}</td><td>{v}</td></tr>")
        return rows

    vehicle_info = data.get("response", {})

    def get_val(*keys, default=None):
        cur = vehicle_info
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur if cur is not None else default

    def to_float(v, default=None):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def to_int(v, default=None):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    def fmt_num(v, digits=1, fallback="--"):
        if v is None:
            return fallback
        return f"{v:.{digits}f}"

    display_name = get_val("display_name", default="My Tesla")
    vin = get_val("vin", default="--")
    state = get_val("state", default="unknown")

    battery_level = to_int(get_val("charge_state", "battery_level"), 0)
    usable_battery_level = to_int(get_val("charge_state", "usable_battery_level"))
    battery_range_mi = to_float(get_val("charge_state", "battery_range"))
    est_battery_range_mi = to_float(get_val("charge_state", "est_battery_range"))
    ideal_battery_range_mi = to_float(get_val("charge_state", "ideal_battery_range"))
    charge_limit = to_int(get_val("charge_state", "charge_limit_soc"))
    charging_state = get_val("charge_state", "charging_state", default="--")
    charge_rate_mph = to_float(get_val("charge_state", "charge_rate"))
    charger_power_kw = to_int(get_val("charge_state", "charger_power"))
    minutes_to_full = to_int(get_val("charge_state", "minutes_to_full_charge"))
    time_to_full = to_float(get_val("charge_state", "time_to_full_charge"))
    charger_voltage = to_int(get_val("charge_state", "charger_voltage"))
    charger_current = to_int(get_val("charge_state", "charger_actual_current"))
    scheduled_charging_mode = get_val("charge_state", "scheduled_charging_mode", default="--")
    charge_port_door_open = bool(get_val("charge_state", "charge_port_door_open", default=False))

    speed_mph = to_float(get_val("drive_state", "speed"), 0.0) or 0.0
    speed_kph = speed_mph * 1.60934
    heading = to_int(get_val("drive_state", "heading"))
    power_kw = to_int(get_val("drive_state", "power"))
    shift_state = get_val("drive_state", "shift_state", default="P")
    lat = get_val("drive_state", "latitude")
    lon = get_val("drive_state", "longitude")
    native_lat = get_val("drive_state", "native_latitude")
    native_lon = get_val("drive_state", "native_longitude")
    native_type = get_val("drive_state", "native_type", default="--")

    inside_temp = to_float(get_val("climate_state", "inside_temp"))
    outside_temp = to_float(get_val("climate_state", "outside_temp"))
    driver_temp_setting = to_float(get_val("climate_state", "driver_temp_setting"))
    passenger_temp_setting = to_float(get_val("climate_state", "passenger_temp_setting"))
    is_climate_on = bool(get_val("climate_state", "is_climate_on", default=False))
    is_auto_conditioning_on = bool(get_val("climate_state", "is_auto_conditioning_on", default=False))
    fan_status = to_int(get_val("climate_state", "fan_status"))
    seat_heater_left = to_int(get_val("climate_state", "seat_heater_left"), 0)
    seat_heater_right = to_int(get_val("climate_state", "seat_heater_right"), 0)
    front_defroster = bool(get_val("climate_state", "is_front_defroster_on", default=False))
    rear_defroster = bool(get_val("climate_state", "is_rear_defroster_on", default=False))

    locked = bool(get_val("vehicle_state", "locked", default=False))
    sentry_mode = bool(get_val("vehicle_state", "sentry_mode", default=False))
    valet_mode = bool(get_val("vehicle_state", "valet_mode", default=False))
    odometer_mi = to_float(get_val("vehicle_state", "odometer"))
    odometer_km = odometer_mi * 1.60934 if odometer_mi is not None else None
    car_version = get_val("vehicle_state", "car_version", default="--")
    api_version = get_val("api_version", default="--")

    software_update = get_val("vehicle_state", "software_update", default={}) or {}
    software_status = software_update.get("status", "--") if isinstance(software_update, dict) else "--"
    software_version = software_update.get("version", "--") if isinstance(software_update, dict) else "--"

    tpms_pressure_fl = to_float(get_val("vehicle_state", "tpms_pressure_fl"))
    tpms_pressure_fr = to_float(get_val("vehicle_state", "tpms_pressure_fr"))
    tpms_pressure_rl = to_float(get_val("vehicle_state", "tpms_pressure_rl"))
    tpms_pressure_rr = to_float(get_val("vehicle_state", "tpms_pressure_rr"))

    door_open = any(
        bool(get_val("vehicle_state", key, default=0))
        for key in ("df", "pf", "dr", "pr", "ft", "rt")
    )

    battery_color = "#36d399" if battery_level >= 50 else "#fbbd23" if battery_level >= 20 else "#f87272"
    circumference = 339
    ring_offset = circumference - (circumference * max(0, min(100, battery_level)) / 100.0)
    moving = speed_mph > 0.1
    online = str(state).lower() == "online"
    charging_on = str(charging_state).lower() in ("charging", "complete")
    updated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    maps_link = f"https://maps.google.com/?q={lat},{lon}" if lat is not None and lon is not None else ""

    table_rows = render_dict(vehicle_info)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{display_name} - {i18n['dashboard']}</title>
    <style>
        :root {{
            --bg: #0b1020;
            --panel: rgba(18, 26, 48, 0.85);
            --panel-border: rgba(148, 163, 184, 0.18);
            --text-main: #e5e7eb;
            --text-muted: #94a3b8;
            --accent: #60a5fa;
            --ok: #36d399;
            --warn: #fbbd23;
            --bad: #f87272;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            color: var(--text-main);
            background:
                radial-gradient(1200px 600px at 5% -10%, rgba(59,130,246,0.25), transparent 55%),
                radial-gradient(1200px 600px at 95% -20%, rgba(14,165,233,0.22), transparent 55%),
                var(--bg);
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            min-height: 100vh;
            padding: 22px;
        }}
        .container {{ max-width: 1240px; margin: 0 auto; }}
        .topbar {{
            display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap;
            margin-bottom: 18px;
        }}
        .link {{
            color: var(--text-muted); text-decoration: none; border: 1px solid var(--panel-border);
            padding: 7px 12px; border-radius: 10px; background: rgba(17, 24, 39, 0.5);
        }}
        .link:hover {{ color: #fff; border-color: rgba(96,165,250,0.5); }}
        .lang {{
            color: var(--text-muted); font-size: 13px;
            border: 1px solid var(--panel-border); padding: 7px 12px; border-radius: 10px;
            background: rgba(17, 24, 39, 0.5);
        }}
        .lang a {{ color: #cbd5e1; text-decoration: none; margin: 0 2px; }}
        .lang a.active {{ color: #fff; font-weight: 600; }}
        .hero {{
            background: linear-gradient(125deg, rgba(37,99,235,0.26), rgba(14,116,144,0.22));
            border: 1px solid rgba(148,163,184,0.22);
            border-radius: 16px; padding: 18px 20px; margin-bottom: 18px;
        }}
        .hero h1 {{ margin: 0; font-size: 24px; font-weight: 650; }}
        .hero-meta {{
            margin-top: 8px; color: var(--text-muted); font-size: 13px; display: flex; gap: 10px; flex-wrap: wrap;
        }}
        .pill {{
            border-radius: 999px; padding: 4px 10px; font-size: 12px; border: 1px solid transparent;
            background: rgba(148,163,184,0.14);
        }}
        .pill.ok {{ color: #d1fae5; background: rgba(16,185,129,0.2); border-color: rgba(16,185,129,0.45); }}
        .pill.bad {{ color: #fee2e2; background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.45); }}
        .grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;
        }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 16px; padding: 16px;
            box-shadow: 0 10px 28px rgba(2, 6, 23, 0.35);
        }}
        .card h3 {{
            margin: 0 0 12px; font-size: 13px; letter-spacing: .06em; text-transform: uppercase; color: var(--text-muted);
        }}
        .metric-row {{
            display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin: 9px 0;
            font-size: 14px;
        }}
        .metric-row b {{ font-size: 20px; font-weight: 650; color: #fff; }}
        .muted {{ color: var(--text-muted); font-size: 12px; }}
        .battery-wrap {{ display: flex; align-items: center; gap: 16px; }}
        .ring {{ position: relative; width: 124px; height: 124px; flex: 0 0 124px; }}
        .ring svg {{ transform: rotate(-90deg); }}
        .ring circle {{ fill: none; stroke-width: 11; }}
        .ring .bg {{ stroke: rgba(148,163,184,0.2); }}
        .ring .fg {{
            stroke: {battery_color}; stroke-linecap: round;
            stroke-dasharray: {circumference}; stroke-dashoffset: {ring_offset};
        }}
        .ring-value {{
            position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
        }}
        .ring-value .big {{ font-size: 30px; font-weight: 700; line-height: 1; color: {battery_color}; }}
        .ring-value .small {{ font-size: 11px; color: var(--text-muted); }}
        .kpi {{
            display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 10px;
        }}
        .kpi .item {{
            padding: 9px 10px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.2); background: rgba(15,23,42,0.45);
        }}
        .kpi .item .v {{ font-size: 17px; font-weight: 650; color: #fff; }}
        .kpi .item .l {{ font-size: 11px; color: var(--text-muted); margin-top: 2px; }}
        .span-2 {{ grid-column: span 2; }}
        .raw {{
            margin-top: 18px; background: var(--panel); border: 1px solid var(--panel-border); border-radius: 14px;
            overflow: hidden;
        }}
        .raw summary {{
            cursor: pointer; padding: 12px 14px; color: var(--text-muted); user-select: none;
        }}
        .raw table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        .raw td {{ padding: 7px 14px; border-top: 1px solid rgba(148,163,184,0.12); vertical-align: top; }}
        .raw td:first-child {{ width: 42%; color: var(--text-muted); word-break: break-all; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="topbar">
                <a class="link" href="/?lang={lang}">← {i18n['back']}</a>
                <div class="lang">
                    {i18n['lang']}: <a class="{'active' if lang == 'zh' else ''}" href="/vehicle/{vid}?lang=zh">中文</a> |
                    <a class="{'active' if lang == 'en' else ''}" href="/vehicle/{vid}?lang=en">English</a>
                </div>
            </div>

            <div class="hero">
                <h1>{display_name} · {i18n['dashboard']}</h1>
                <div class="hero-meta">
                    <span>VIN: {vin}</span>
                    <span>{i18n['updated']}: {updated_at}</span>
                    <span class="pill {'ok' if online else 'bad'}">{i18n['online'] if online else i18n['offline']}</span>
                    <span class="pill {'ok' if charging_on else 'bad'}">{i18n['charging_on'] if charging_on else i18n['charging_off']}</span>
                </div>
            </div>

            <div class="grid">
                <section class="card">
                    <h3>{i18n['battery']}</h3>
                    <div class="battery-wrap">
                        <div class="ring">
                            <svg width="124" height="124">
                                <circle class="bg" cx="62" cy="62" r="54"></circle>
                                <circle class="fg" cx="62" cy="62" r="54"></circle>
                            </svg>
                            <div class="ring-value">
                                <div class="big">{battery_level}%</div>
                                <div class="small">{i18n['battery']}</div>
                            </div>
                        </div>
                        <div style="flex:1;">
                            <div class="metric-row"><span>Usable SoC</span><b>{usable_battery_level if usable_battery_level is not None else '--'}%</b></div>
                            <div class="metric-row"><span>Rated Range</span><b>{fmt_num(battery_range_mi)} mi</b></div>
                            <div class="muted">Est: {fmt_num(est_battery_range_mi)} mi · Ideal: {fmt_num(ideal_battery_range_mi)} mi</div>
                        </div>
                    </div>
                    <div class="kpi">
                        <div class="item"><div class="v">{charge_limit if charge_limit is not None else '--'}%</div><div class="l">Charge Limit</div></div>
                        <div class="item"><div class="v">{charging_state}</div><div class="l">Charging State</div></div>
                    </div>
                </section>

                <section class="card">
                    <h3>{i18n['driving']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{fmt_num(speed_mph)} mph</div><div class="l">Speed</div></div>
                        <div class="item"><div class="v">{fmt_num(speed_kph)} km/h</div><div class="l">Speed (Metric)</div></div>
                        <div class="item"><div class="v">{shift_state or '--'}</div><div class="l">Shift State</div></div>
                        <div class="item"><div class="v">{power_kw if power_kw is not None else '--'} kW</div><div class="l">Power</div></div>
                        <div class="item span-2"><div class="v">{i18n['moving'] if moving else i18n['parked']}</div><div class="l">Vehicle Motion</div></div>
                    </div>
                    <div class="muted">Heading: {heading if heading is not None else '--'}°</div>
                </section>

                <section class="card">
                    <h3>{i18n['charging']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{fmt_num(charge_rate_mph)} mph</div><div class="l">Charge Rate</div></div>
                        <div class="item"><div class="v">{charger_power_kw if charger_power_kw is not None else '--'} kW</div><div class="l">Charger Power</div></div>
                        <div class="item"><div class="v">{minutes_to_full if minutes_to_full is not None else '--'} min</div><div class="l">Minutes To Full</div></div>
                        <div class="item"><div class="v">{fmt_num(time_to_full, 2)} h</div><div class="l">Time To Full</div></div>
                        <div class="item"><div class="v">{charger_voltage if charger_voltage is not None else '--'} V</div><div class="l">Voltage</div></div>
                        <div class="item"><div class="v">{charger_current if charger_current is not None else '--'} A</div><div class="l">Actual Current</div></div>
                        <div class="item span-2"><div class="v">{scheduled_charging_mode}</div><div class="l">Scheduled Charging Mode</div></div>
                    </div>
                    <div class="muted">Charge Port Door Open: {i18n['yes'] if charge_port_door_open else i18n['no']}</div>
                </section>

                <section class="card">
                    <h3>{i18n['climate']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{fmt_num(inside_temp)}°C</div><div class="l">Inside Temp</div></div>
                        <div class="item"><div class="v">{fmt_num(outside_temp)}°C</div><div class="l">Outside Temp</div></div>
                        <div class="item"><div class="v">{fmt_num(driver_temp_setting)}°C</div><div class="l">Driver Setpoint</div></div>
                        <div class="item"><div class="v">{fmt_num(passenger_temp_setting)}°C</div><div class="l">Passenger Setpoint</div></div>
                        <div class="item"><div class="v">{fan_status if fan_status is not None else '--'}</div><div class="l">Fan Level</div></div>
                        <div class="item"><div class="v">{i18n['yes'] if is_auto_conditioning_on else i18n['no']}</div><div class="l">Auto Conditioning</div></div>
                        <div class="item"><div class="v">L{seat_heater_left}</div><div class="l">Seat Heater Left</div></div>
                        <div class="item"><div class="v">R{seat_heater_right}</div><div class="l">Seat Heater Right</div></div>
                    </div>
                    <div class="muted">Climate On: {i18n['yes'] if is_climate_on else i18n['no']} · Front Defrost: {i18n['yes'] if front_defroster else i18n['no']} · Rear Defrost: {i18n['yes'] if rear_defroster else i18n['no']}</div>
                </section>

                <section class="card">
                    <h3>{i18n['security']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{i18n['locked'] if locked else i18n['unlocked']}</div><div class="l">Door Lock</div></div>
                        <div class="item"><div class="v">{i18n['yes'] if sentry_mode else i18n['no']}</div><div class="l">Sentry Mode</div></div>
                        <div class="item"><div class="v">{i18n['yes'] if valet_mode else i18n['no']}</div><div class="l">Valet Mode</div></div>
                        <div class="item"><div class="v">{i18n['open_detected'] if door_open else i18n['all_closed']}</div><div class="l">Door / Trunk</div></div>
                    </div>
                </section>

                <section class="card">
                    <h3>{i18n['software']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{car_version}</div><div class="l">Car Version</div></div>
                        <div class="item"><div class="v">{software_status}</div><div class="l">Update Status</div></div>
                        <div class="item"><div class="v">{software_version}</div><div class="l">Update Version</div></div>
                        <div class="item"><div class="v">{api_version}</div><div class="l">API Version</div></div>
                        <div class="item"><div class="v">{fmt_num(odometer_mi)} mi</div><div class="l">Odometer</div></div>
                        <div class="item"><div class="v">{fmt_num(odometer_km)} km</div><div class="l">Odometer (Metric)</div></div>
                    </div>
                </section>

                <section class="card">
                    <h3>{i18n['tires']}</h3>
                    <div class="kpi">
                        <div class="item"><div class="v">{fmt_num(tpms_pressure_fl)} bar</div><div class="l">Front Left</div></div>
                        <div class="item"><div class="v">{fmt_num(tpms_pressure_fr)} bar</div><div class="l">Front Right</div></div>
                        <div class="item"><div class="v">{fmt_num(tpms_pressure_rl)} bar</div><div class="l">Rear Left</div></div>
                        <div class="item"><div class="v">{fmt_num(tpms_pressure_rr)} bar</div><div class="l">Rear Right</div></div>
                    </div>
                </section>

                <section class="card">
                    <h3>{i18n['location']}</h3>
                    <div class="kpi">
                        <div class="item span-2"><div class="v">{lat if lat is not None else '--'}, {lon if lon is not None else '--'}</div><div class="l">WGS84 Coordinates</div></div>
                        <div class="item span-2"><div class="v">{native_lat if native_lat is not None else '--'}, {native_lon if native_lon is not None else '--'}</div><div class="l">Native Coordinates ({native_type})</div></div>
                    </div>
                    {"<a class='link' target='_blank' href='" + maps_link + "'>📍 " + i18n["map"] + "</a>" if maps_link else "<div class='muted'>Map link unavailable</div>"}
                </section>
            </div>

            <details class="raw">
                <summary>📊 {i18n['raw']} ({len(table_rows)} fields)</summary>
                <table>{''.join(table_rows)}</table>
            </details>
        </div>
    </body>
    </html>
    """
    return html


@app.route('/.well-known/appspecific/<path:filename>')
def well_known(filename):
    return send_from_directory('.well-known/appspecific', filename)

app.run(port=8080, debug=False)
