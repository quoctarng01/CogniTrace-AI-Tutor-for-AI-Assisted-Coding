from tracer.tracer import run_trace, _build_instr_map, _build_offset_to_line, _detect_branch
import dis

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

print("=== offset_to_line ===")
for off, line in sorted(offset_to_line.items()):
    print(f"  offset={off} -> line={line}")

print()
print("=== Running trace ===")
result = run_trace(code)
print(f"error={result['error']}")
print(f"total_steps={result['total_steps']}")
print()
for s in result['steps']:
    print(f"  step={s['step_number']} line={s['line_number']} opcode={s['opcode']} branches={s['branches_taken']} return={s['return_value']}")
