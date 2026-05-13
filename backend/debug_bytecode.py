import dis, ast

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code.strip(), "<test>", "exec")
print("=== Bytecode ===")
dis.dis(compiled)

print()
print("=== AST lines ===")
tree = ast.parse(code)
for node in ast.walk(tree):
    if hasattr(node, 'lineno'):
        print(f"{node.__class__.__name__} at line {node.lineno}")
