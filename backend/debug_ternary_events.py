import sys

events = []

def tracer(frame, event, arg):
    events.append((event, frame.f_code.co_name, frame.f_lineno, frame.f_lasti))
    return tracer

code = """
x = 10
result = "big" if x > 5 else "small"
"""

compiled = compile(code, "<test>", "exec")
sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
sys.settrace(None)

for event, name, lineno, lasti in events:
    print(f"  {event:<8} line={lineno}  lasti={lasti}")
