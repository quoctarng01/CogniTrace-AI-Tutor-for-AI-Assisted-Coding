# Security & Sandbox Model

> **Required reading before any production deployment.**

CogniTrace executes user-submitted Python code in order to produce the execution trace that drives its AI explanations. Executing arbitrary code is inherently dangerous. This document describes the current defense-in-depth sandbox and explicitly enumerates the residual risks so the deployment team can decide whether additional isolation is required.

---

## 1. Threat model

**Adversary.** A user submits a Python snippet through the `POST /api/traces/run` endpoint. The snippet may contain code that attempts to:

- Read or write the host filesystem.
- Make outbound network connections.
- Exhaust CPU, memory, or file descriptor limits.
- Escape the Python sandbox to access the host kernel.
- Subvert the tracer by reaching into the tracer's `__globals__`, `__code__`, or `__subclasses__()` chains.
- Cause a denial-of-service by spawning processes, threads, or generators that outlive the trace.
- Read environment variables or other secrets from the host.

The validator and the runtime sandbox together address each of these vectors. Below is the current model; the residual risk section (Section 4) lists what these defenses do **not** catch.

---

## 2. Two-tier sandbox

### Tier 1 — Static AST validation (`backend/tracer/validator.py`)

The validator runs **before** the subprocess is spawned. It walks the AST and rejects code that contains:

| Pattern | Reason blocked |
|---|---|
| `import os`, `import sys`, `import subprocess`, `import ctypes`, `import resource`, `import socket`, `import multiprocessing`, `import threading`, `import mmap`, `import pty`, `import signal`, `import gc`, `import pickle`, `import importlib`, … | Modules that touch the OS, network, or interpreter internals |
| `eval(`, `exec(`, `compile(`, `open(`, `__import__(`, `getattr(`, `setattr(`, `input(`, `breakpoint(`, `vars(`, `globals(`, `locals(`, `memoryview(`, `dir(` | Builtins that bypass the AST analysis or expose internals |
| `.attr` where `attr` is a dunder (`__name__`, `__class__`, `__subclasses__`, `__globals__`, `__code__`, …) | The classic Python sandbox-escape chain (`obj.__class__.__mro__[1].__subclasses__()`) |
| `match/case` statements | Branch detection does not yet cover these constructs; allowing them would silently omit branch chips |
| `while <truthy>: yield …` | Generator-based DoS — the generator body runs unbounded on first iteration, evading the step counter |

The validator is the **first line of defense**. It runs in the FastAPI process and is therefore the cheapest layer. See `backend/tracer/validator.py` for the full denylist.

### Tier 2 — Dynamic subprocess sandbox (`backend/tracer/runner.py`)

After validation passes, the code runs in a separate Python subprocess with:

| Limit | Value | Purpose |
|---|---|---|
| Wall-clock timeout | 5 seconds | Prevents infinite loops and CPU starvation |
| Step ceiling | 500 trace steps | Caps total work even on highly nested code |
| `RLIMIT_AS` (address space) | 256 MB | Prevents memory-exhaustion attacks |
| `RLIMIT_CPU` (CPU time) | 4 seconds | Outer backstop on the 5-second timeout |
| `RLIMIT_NPROC` | 0 (no new processes) | Blocks `os.fork()` from inside the sandbox |
| `sys.settrace()` callback | Always installed | Captures every line/event for the trace |
| Sealed filename | `<codescope>` | The tracer skips any frame not under this filename, so imported stdlib doesn't pollute the trace |

The subprocess is spawned via `subprocess.run(timeout=5s, …)` from the FastAPI process. Communication is via JSON over stdout/stdin (not pipes shared with the parent's environment).

### Tier 3 — Application-level guards

- The dynamic tracer itself contains an `_INTERNAL_NAMES` filter so that even if a frame leaks through with the `<codescope>` filename, internal variables (`__builtins__`, `namespace`, `_branch_decisions`, …) are hidden from the trace output.
- Branch detection (Workstream 5) **compiles `if` conditions into lambdas at build time** and invokes them with the namespace at runtime. There is no `eval()` call inside the tracer callback. This closes the most well-known Python sandbox-escape vector.

---

## 3. What is NOT in scope of the current sandbox

These are **not** addressed by the current model and **must** be addressed before any public-facing deployment:

1. **OS-level container isolation.** The subprocess runs in the same OS as the FastAPI process. A successful escape from the Python sandbox (via a Python interpreter bug, an unknown dunder, or a new attack surface in an allowed module) gives the attacker the host user's privileges. Mitigation: deploy the tracer container with `read_only: true`, `tmpfs` mounts for ephemeral state, a non-root user (UID 1000), and (preferred) a microVM boundary (Firecracker, gVisor, or kata-containers).
2. **Network policy.** The current model allows `socket` access if the user imports it via an alias that bypasses the denylist (e.g., `from importlib import import_module; import_module("socket")`). The denylist should be supplemented with a kernel-level seccomp filter that blocks `socket(2)`, `connect(2)`, `bind(2)`, and `listen(2)` syscalls inside the subprocess.
3. **Filesystem policy.** Even with `read_only` mounts, the attacker may be able to write to `/tmp` or `/dev/shm`. Mitigation: bind-mount an empty `tmpfs` and overlay only the files required for the trace (the temp `.py` source file).
4. **Resource accounting across requests.** A user could open a long-lived subprocess by submitting slow code that passes the step counter but takes 4.99s per trace. Mitigation: per-user subprocess concurrency cap (`MAX_CONCURRENT_TRACES_PER_USER` in `backend/app/config.py`).
5. **Side channels.** The tracer captures the full namespace into the response. If the user's code accesses secrets via runtime introspection (e.g., `os.environ`), those secrets could appear in the trace JSON. Mitigation: replace `os` and `sys` in the namespace dict with safe replacements *before* `_capture_variables` runs, or wipe the captured namespace before returning.
6. **LLM provider abuse.** The LLM endpoints are rate-limited (`/api/llm/explain/stream`, `/api/llm/diagnose`), but the limits are per-IP and per-token-suffix. A motivated attacker with multiple JWTs can drive up provider cost. Mitigation: a global cost cap per user per day, enforced at the `llm_telemetry` layer (Workstream 6).

---

## 4. Residual risk matrix

| Vector | Probability | Impact | Mitigation status |
|---|---|---|---|
| Known dunder escape (`__subclasses__`) | Low | Critical | ✅ Blocked by validator (extended denylist, Workstream 5) |
| Unknown dunder escape | Low | Critical | ⚠️ Validator rejects all dunders (Workstream 5); a future unknown dunder could evade. Mitigation: deploy in a microVM. |
| `eval()` reintroduction by refactor | Medium | Critical | ✅ `test_tracer_eval_removed.py` asserts `eval()` never appears in tracer source. |
| CPU exhaustion (infinite loop) | Medium | Medium | ✅ 5-second `subprocess.run` timeout + `RLIMIT_CPU` |
| Memory exhaustion | Medium | Medium | ✅ `RLIMIT_AS` 256 MB |
| Generator-based DoS | Medium | Medium | ✅ Validator rejects `while <truthy>: yield …` |
| Filesystem write | Low | High | ⚠️ Container isolation required (`read_only: true` + tmpfs) |
| Network egress | Low | High | ⚠️ Seccomp filter required |
| Process spawning | Low | High | ✅ `RLIMIT_NPROC = 0` + denylisted modules |
| LLM cost exhaustion | Medium | Medium | ⚠️ Per-user cost cap not yet enforced (Workstream 6) |
| Secret exfiltration via trace JSON | Low | High | ⚠️ Captured namespace should be sanitized |

---

## 5. Deployment checklist

Before deploying CogniTrace to any environment that executes code from untrusted users:

- [ ] Run the tracer container with `read_only: true` and `user: "1000:1000"` in `docker-compose.yml`. (Implemented in Workstream 7.)
- [ ] Apply a seccomp profile that blocks `socket(2)`, `connect(2)`, `bind(2)`, `listen(2)`, `ptrace(2)`, and `mount(2)` inside the tracer container.
- [ ] Set the tracer container's memory limit to 512 MB (4× the per-process `RLIMIT_AS`).
- [ ] Configure the LLM provider with a per-user cost cap (currently a Workstream 6 item).
- [ ] Run the full `backend/tests/unit/test_sandbox_bypass.py` suite against the deployment image.
- [ ] Run `grep -n 'eval(' backend/tracer/` and confirm zero matches. (Enforced by `test_tracer_eval_removed.py`.)
- [ ] Verify the subprocess source filename (`<codescope>`) is not overridable from user code.

---

## 6. Reporting

If you discover a bypass, please report it to the project maintainer. Do not disclose publicly until a fix is shipped.

---

## 7. Test surface

The sandbox is regression-tested by:

- `backend/tests/unit/test_validator.py` — every denylisted pattern is asserted blocked.
- `backend/tests/unit/test_sandbox_bypass.py` — classic escape attempts (`__subclasses__`, `__globals__`, etc.).
- `backend/tests/unit/test_branch_detection_safe.py` — Workstream 5: branch compilation safety.
- `backend/tests/unit/test_tracer_eval_removed.py` — Workstream 5: `eval()` is never called.

Any new attack vector must come with a regression test before being marked resolved.
