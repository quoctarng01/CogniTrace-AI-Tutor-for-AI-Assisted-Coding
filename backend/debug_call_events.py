import sys

events = []

def tracer(frame, event, arg):
    events.append((event, frame.f_code.co_name, frame.f_lineno, frame.f_lasti, arg))
    return tracer

code = """
def add(a, b):
    return a + b
result = add(2, 3)
"""

compiled = compile(code, "<test>", "exec")
sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)

for event, name, lineno, lasti, arg in events:
    print(f"  {event:<8} {name:<12} line={lineno:<3} lasti={lasti:<3}  arg={arg!r}")
