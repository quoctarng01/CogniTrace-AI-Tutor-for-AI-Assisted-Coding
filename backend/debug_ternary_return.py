import dis

# Ternary
code2 = """
x = 10
result = "big" if x > 5 else "small"
"""
c2 = compile(code2, "<test>", "exec")
print("=== TERNARY bytecode ===")
dis.dis(c2)

print()

# Function return
code3 = """
def add(a, b):
    return a + b
result = add(2, 3)
"""
c3 = compile(code3, "<test>", "exec")
print("=== FUNCTION RETURN bytecode ===")
dis.dis(c3)
