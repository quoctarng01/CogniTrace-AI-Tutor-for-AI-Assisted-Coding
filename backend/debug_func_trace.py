from tracer.tracer import run_trace
import sys

code = """
def add(a, b):
    return a + b

result = add(2, 3)
"""

print("=== Running trace ===")
result = run_trace(code)
print(f"error={result['error']}")
print(f"total_steps={result['total_steps']}")
print()
for s in result['steps']:
    print(f"  step={s['step_number']} line={s['line_number']} opcode={s['opcode']} return={s['return_value']} vars={s['variables']}")
