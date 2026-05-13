from tracer.tracer import run_trace, _build_instr_map, _build_offset_to_line
import sys, dis

code = """
def add(a, b):
    return a + b

result = add(2, 3)
"""

compiled = compile(code, '<test>', 'exec')
instr_map = _build_instr_map(compiled)
offset_to_line = _build_offset_to_line(compiled)

print("=== All offsets -> lines ===")
for off, line in sorted(offset_to_line.items()):
    print(f"  offset={off} -> line={line}")

print()
print("=== Tracing events ===")

pending_return = None
events = []

def tracer(frame, event, arg):
    global pending_return
    lineno = frame.f_lineno
    lasti = frame.f_lasti
    depth = 0
    cur = frame.f_back
    while cur:
        depth += 1
        cur = cur.f_back

    if event == 'return':
        rv = repr(arg) if arg is not None else None
        if frame.f_back:
            pending_return = (frame.f_back.f_lineno, rv)
        print(f"  RETURN lineno={lineno} lasti={lasti} depth={depth} -> pending_return={pending_return}")
    elif event == 'line':
        print(f"  LINE   lineno={lineno} lasti={lasti} depth={depth} pending_return={pending_return}")
        if pending_return:
            print(f"    -> WILL CONSUME pending_return (call_line={pending_return[0]})")
            pending_return = None
    else:
        print(f"  {event.upper():6s} lineno={lineno} lasti={lasti} depth={depth}")
    return tracer

sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)

print()
print("=== Final state ===")
print(f"pending_return={pending_return}")
print()
print("=== offset_to_line for high offsets ===")
for off in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26]:
    print(f"  offset={off} -> line={offset_to_line.get(off, 'NOT FOUND')}")
