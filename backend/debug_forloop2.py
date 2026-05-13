import sys, dis

events = []

def tracer(frame, event, arg):
    from tracer.tracer import _build_instr_map
    instr_map = _build_instr_map(frame.f_code) if frame.f_code else {}
    curr_lasti = frame.f_lasti
    curr_opcode = instr_map.get(curr_lasti, ("?", 0))[0] if instr_map else "?"
    prev_lasti = curr_lasti - 2 if curr_lasti >= 2 else 0
    prev_opcode = instr_map.get(prev_lasti, ("?", 0))[0] if instr_map else "?"
    events.append((event, frame.f_code.co_name, frame.f_lineno, curr_lasti, curr_opcode, prev_lasti, prev_opcode, arg))
    return tracer

code = """
total = 0
for i in range(3):
    total += i
"""

compiled = compile(code, "<test>", "exec")
sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)

for event, name, lineno, curr_lasti, curr_op, prev_lasti, prev_op, arg in events:
    print(f"  {event:<8} {name:<10} line={lineno:<3} curr={curr_lasti}({curr_op:<22}) prev={prev_lasti}({prev_op:<22})  arg={arg!r}")
