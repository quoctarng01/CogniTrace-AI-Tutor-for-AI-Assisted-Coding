"""Generate a real session JWT via admin API and test the trajectory endpoint."""
import urllib.request, urllib.error, json
from urllib.parse import urlencode
from collections import Counter, defaultdict

URL = "https://cyzpvltrayvpdooxgmaj.supabase.co"
KEY_S = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5enB2bHRyYXl2cGRvb3hnbWFqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODEzOTc3NCwiZXhwIjoyMDkzNzE1Nzc0fQ.0JMJHwPfqXJW_cIEb1kIcQhXSJ4j28yEVNz64R8vWIM"

def req(method, path, body=None, headers=None):
    headers = headers or {"apikey": KEY_S, "Authorization": f"Bearer {KEY_S}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

# Create a session link / impersonation
# Admin API: POST /auth/v1/admin/users/{user_id}/sessions → creates a session
USER_ID = "468a059a-85c5-4057-bbfb-19e6e5d61cb6"  # quoctrang613
code, body = req("POST", f"/auth/v1/admin/users/{USER_ID}/sessions", {})
print(f"=== POST /auth/v1/admin/users/{USER_ID[:8]}/sessions ===")
print(f"  HTTP {code}")
if isinstance(body, dict):
    token = body.get("access_token")
    print(f"  access_token: {token[:60] if token else 'NONE'}...")
    refresh = body.get("refresh_token")
    print(f"  refresh_token: {refresh[:30] if refresh else 'NONE'}...")

    if token:
        print("\n=== GET http://localhost:8001/api/review/trajectory?days=30 ===")
        r = urllib.request.Request(
            "http://localhost:8001/api/review/trajectory?days=30",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                print(f"  HTTP {resp.status}")
                data = json.loads(resp.read().decode())
                print(f"  total_events: {data.get('total_events')}")
                print(f"  days: {data.get('days')}")
                print(f"  date_range: {data.get('date_range')}")
                print(f"  concepts ({len(data.get('concepts', []))}):")
                for c in data.get('concepts', [])[:6]:
                    pts = c.get('points', [])
                    print(f"    {c.get('concept_tag')}: {len(pts)} points, current={c.get('current_mastery')}, recent_miss={c.get('recent_miss')}")
                    if pts:
                        print(f"      first: {pts[0]}")
                        print(f"      last:  {pts[-1]}")
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
else:
    print(f"  body: {body}")
