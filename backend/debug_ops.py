import dis

# For loop
code1 = """
total = 0
for i in range(3):
    total += i
"""
c1 = compile(code1, "<test>", "exec")
print("=== FOR LOOP ===")
for instr in dis.get_instructions(c1):
    print(f"  {instr.offset}: {instr.opname}")

print()

# Ternary
code2 = """
x = 10
result = "big" if x > 5 else "small"
"""
c2 = compile(code2, "<test>", "exec")
print("=== TERNARY ===")
for instr in dis.get_instructions(c2):
    print(f"  {instr.offset}: {instr.opname}")

print()

# Function return
code3 = """
def add(a, b):
    return a + b
result = add(2, 3)
"""
c3 = compile(code3, "<test>", "exec")
print("=== FUNCTION RETURN ===")
for instr in dis.get_instructions(c3):
    print(f"  {instr.offset}: {instr.opname}")
