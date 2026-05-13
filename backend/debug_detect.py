from tracer.tracer import run_trace, _build_instr_map, _build_offset_to_line, _detect_branch, _parse_ast_for_jumps
import dis, ast

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code, '<test>', 'exec')
instr_map = _build_instr_map(compiled)
offset_to_line = _build_offset_to_line(compiled)
tree = ast.parse(code)

print("=== instr_map (non-RESUME/LOAD/STORE) ===")
for off, (op, arg) in sorted(instr_map.items()):
    if 'RESUME' in op or 'LOAD' in op or 'STORE' in op or 'RETURN' in op or 'COMPARE' in op:
        continue
    line = offset_to_line.get(off, '?')
    print(f"  offset={off:3d} op={op:25s} arg={arg:3d}  line={line}")

print()
print("=== AST jump targets ===")
targets = _parse_ast_for_jumps(tree)
for line, (body, is_else) in sorted(targets.items()):
    print(f"  line {line} -> body_line={body}, is_else={is_else}")

print()
print("=== Simulate _detect_branch for each trace event ===")
import sys as _sys

events = []
def tracer(frame, event, arg):
    events.append((frame.f_lineno, frame.f_lasti, event))
    return tracer

_sys.settrace(tracer)
exec(compiled, {"__name__": "__test__"})
_sys.settrace(None)

loop_iterations = {}
for lineno, lasti, event in events:
    if event == 'line':
        result = _detect_branch(lasti, lineno, instr_map, offset_to_line, loop_iterations)
        print(f"  line={lineno}, lasti={lasti}, branch={result}")
