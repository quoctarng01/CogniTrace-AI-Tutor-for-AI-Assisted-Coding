from tracer.tracer import run_trace

code = """
x = 10
result = "big" if x > 5 else "small"
"""
r = run_trace(code)
print("Steps:")
for s in r["steps"]:
    print(f"  step={s['step_number']} line={s['line_number']} lasti={s['bytecode_offset']} opcode={s['opcode']} branches={s['branches_taken']} return={s.get('return_value')}")
