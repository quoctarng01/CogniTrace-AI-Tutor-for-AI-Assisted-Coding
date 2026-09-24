import subprocess, os, sys

# 1. Start uvicorn on 8001
print("Starting uvicorn on port 8001...")
p = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--host", "127.0.0.1"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
print(f"Started PID {p.pid}")
import time
time.sleep(3)
# Check if it started
result = subprocess.run('cmd /c "netstat -ano | findstr :8001 | findstr LISTENING"',
                       capture_output=True, text=True)
if result.stdout.strip():
    print("Backend is UP on port 8001")
else:
    print("Backend may not have started, check output above")
    stdout, _ = p.communicate(timeout=1)
    print(stdout[:500])
