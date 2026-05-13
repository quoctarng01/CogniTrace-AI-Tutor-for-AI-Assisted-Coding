import sys, dis

events = []

def tracer(frame, event, arg):
    code = frame.f_code
    events.append((event, code.co_name, frame.f_lineno, frame.f_lasti, arg))
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

for event, name, lineno, lasti, arg in events:
    print(f"  {event:<12} {name:<12} line={lineno:<3} lasti={lasti:<3}  arg={arg!r}")
