import dis

# For loop
code1 = """
total = 0
for i in range(3):
    total += i
"""
c1 = compile(code1, "<test>", "exec")
print("=== FOR LOOP bytecode with lines ===")
dis.dis(c1)

# Function return
code3 = """
def add(a, b):
    return a + b
result = add(2, 3)
"""
c3 = compile(code3, "<test>", "exec")
print()
print("=== FUNCTION RETURN bytecode ===")
dis.dis(c3)
