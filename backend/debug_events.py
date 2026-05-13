import sys, dis

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code, '<test>', 'exec')

print("=== Instruction map ===")
instr_map = {}
for instr in dis.get_instructions(compiled):
    instr_map[instr.offset] = (instr.opname, instr.arg if instr.arg is not None else 0)
    print(f"  offset={instr.offset:3d} opname={instr.opname:25s} arg={instr.arg}")

print()
print("=== Tracing events ===")
def trace(frame, event, arg):
    print(f"  event={event:8s} lineno={frame.f_lineno:3d} lasti={frame.f_lasti:3d}")
    return trace

sys.settrace(trace)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)
