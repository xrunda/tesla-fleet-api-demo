
from flask import Flask, redirect, request, send_from_directory
import secrets, requests, urllib.parse, time, os

app = Flask(__name__)

CLIENT_ID = "your-tesla-client-id"
CLIENT_SECRET = "your-tesla-client-secret"
REDIRECT_URI = "https://your-unique-ngrok-name.ngrok-free.dev/auth/callback"
SCOPES = "openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds"
STATE = secrets.token_urlsafe(32)

class TeslaAPI:
    def __init__(self, client_id, client_secret, redirect_uri, scopes):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.tokens = {}
        self.state = STATE

    def valid(self):
        return self.tokens and (int(time.time()) - self.tokens["obtained_at"] < self.tokens["expires_in"] - 60)

    def refresh(self):
        r = requests.post("https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token", data={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.tokens["refresh_token"]
        }).json()
        r["obtained_at"] = int(time.time())
        self.tokens.update(r)

    def api_get(self, path):
        if not self.valid():
            self.refresh()
        return requests.get(
            f"https://fleet-api.prd.na.vn.cloud.tesla.com{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}"}
        )

    def api_post(self, path):
        if not self.valid():
            self.refresh()
        return requests.post(
            f"https://fleet-api.prd.na.vn.cloud.tesla.com{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}"}
        )

    def get_vehicles(self):
        resp = self.api_get("/api/1/vehicles")
        try:
            return resp.json().get('response', [])
        except Exception:
            return []

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
        url = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/authorize?" + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "state": tesla_api.state
        })
        return f"<h1>Tesla Fleet</h1><a href='{url}'>Login with Tesla</a>"
    cars = tesla_api.get_vehicles()
    return "<h1>Your Vehicles</h1>" + "".join(
        f"<p><a href='/vehicle/{c['id']}'>{c['display_name']} ({c['vin']})</a></p>"
        for c in cars
    )

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

    resp = requests.post("https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token", data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    })
    if resp.status_code != 200:
        return f"<h1>Token Exchange Failed</h1><pre>{resp.text}</pre>", 400
    token = resp.json()
    token["obtained_at"] = int(time.time())
    tesla_api.tokens.update(token)
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
