import dis

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code.strip(), "<test>", "exec")

for instr in dis.get_instructions(compiled):
    pos = instr.positions
    print(f"{instr.offset}: {instr.opname:<30} lineno={pos.lineno}")
