"""Start a fresh uvicorn backend on port 8001, then patch frontend to use it."""
import subprocess, os, sys, time, urllib.request, json

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BACKEND_DIR, "..", "frontend")

# 1. Verify port 8001 is free
result = subprocess.run('cmd /c "netstat -ano | findstr :8001 | findstr LISTENING"',
                       capture_output=True, text=True)
if result.stdout.strip():
    print("Port 8001 is already in use!")
    print(result.stdout)
    sys.exit(1)
print("Port 8001 is free")

# 2. Start uvicorn on 8001
print("\nStarting uvicorn on 8001...")
p = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app",
     "--port", "8001", "--host", "127.0.0.1"],
    cwd=BACKEND_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
print(f"PID {p.pid}")
time.sleep(4)

# 3. Verify it's up
try:
    with urllib.request.urlopen("http://127.0.0.1:8001/", timeout=5) as r:
        print(f"Backend health: HTTP {r.status}")
except Exception as e:
    print(f"Backend health check failed: {e}")
    stdout, _ = p.communicate(timeout=1)
    print("Backend stdout:", stdout[:500])

# 4. Check trajectory route
try:
    with urllib.request.urlopen("http://127.0.0.1:8001/api/review/trajectory", timeout=5) as r:
        print(f"trajectory (no auth): HTTP {r.status}")
except urllib.request.HTTPError as e:
    print(f"trajectory (no auth): HTTP {e.code} (expected 401)")

# 5. Patch frontend .env.local
env_local = os.path.join(FRONTEND_DIR, ".env.local")
api_url = "http://localhost:8001"
content = f"NEXT_PUBLIC_API_URL={api_url}\n"
with open(env_local, "w") as f:
    f.write(content)
print(f"\nPatched {env_local}:")
print(content)

# 6. Restart frontend dev server (need to find its PID)
result = subprocess.run('cmd /c "netstat -ano | findstr :3000 | findstr LISTENING"',
                       capture_output=True, text=True)
print("\nFrontend processes on 3000:")
print(result.stdout or "(none)")

print("\n\nNow do these steps manually:")
print(f"1. Kill the frontend dev server (port 3000)")
print("2. Run: cd frontend && npm run dev")
print("3. Visit: http://127.0.0.1:3000/auth/login")
print("4. Sign in via GitHub as quoctrang613@gmail.com")
print("5. Navigate to: http://127.0.0.1:3000/dashboard/mastery")
