import dis, ast, sys

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code.strip(), "<test>", "exec")

# Build offset → line map using co_positions() (Python 3.12+)
print("=== Offset to line map ===")
for instr in dis.get_instructions(compiled):
    try:
        positions = instr.positions()
        if positions.lineno is not None:
            print(f"  offset {instr.offset:3d}: {instr.opname:<25} line={positions.lineno}")
    except Exception:
        print(f"  offset {instr.offset:3d}: {instr.opname:<25} (no line)")

print()
print("=== Tracing events ===")
events = []

def tracer(frame, event, arg):
    f_lasti = frame.f_lasti
    f_lineno = frame.f_lineno
    try:
        positions = frame.f_code.co_positions()
        # f_lineno is reliable
    except:
        pass
    events.append((event, f_lineno, f_lasti))
    return tracer

sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)

for event, lineno, lasti in events:
    print(f"  event={event:<12} line={lineno:<3} lasti={lasti}")
