from tracer.tracer import run_trace

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""
result = run_trace(code)
print("error:", result.get("error"))
print("total_steps:", result["total_steps"])
for s in result["steps"]:
    print(f"Step {s['step_number']}: line={s['line_number']} opcode={s['opcode']} branches={s['branches_taken']}")
