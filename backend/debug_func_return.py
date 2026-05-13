from tracer.tracer import run_trace

# Function return
code3 = """
def add(a, b):
    return a + b
result = add(2, 3)
"""
r3 = run_trace(code3)
print("FUNCTION RETURN:")
for s in r3["steps"]:
    print(f"  line={s['line_number']} opcode={s['opcode']} vars={list(s['variables'].keys())} return={s.get('return_value')}")
print(f"  total_steps: {r3['total_steps']}")
