from tracer.tracer import run_trace

# Test for loop
code = """
total = 0
for i in range(3):
    total += i
"""
r = run_trace(code)
print("FOR LOOP:")
for s in r["steps"]:
    if s["branches_taken"]:
        print(f"  line={s['line_number']} branches={s['branches_taken']}")

# Test ternary
code2 = """
x = 10
result = "big" if x > 5 else "small"
"""
r2 = run_trace(code2)
print()
print("TERNARY:")
for s in r2["steps"]:
    print(f"  line={s['line_number']} opcode={s['opcode']} branches={s['branches_taken']}")

# Test function return
code3 = """
def add(a, b):
    return a + b
result = add(2, 3)
"""
r3 = run_trace(code3)
print()
print("FUNCTION RETURN:")
for s in r3["steps"]:
    if s.get("return_value") is not None:
        print(f"  line={s['line_number']} return_value={s['return_value']}")
print("  total_steps:", r3["total_steps"])
