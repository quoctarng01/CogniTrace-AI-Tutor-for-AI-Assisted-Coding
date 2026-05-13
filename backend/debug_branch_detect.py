from tracer.tracer import run_trace, _build_instr_map, _detect_branch

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code.strip(), "<test>", "exec")
instr_map = _build_instr_map(compiled)

# For if x > 5 (line 3):
# POP_JUMP_IF_FALSE is at offset 14
# if-body starts at offset 16
# When we enter if-body (offset 16, line 3):
#   curr_lasti = 16, curr_opcode = LOAD_CONST
#   prev_lasti = 14, prev_opcode = POP_JUMP_IF_FALSE
print("=== Simulating if-branch detection ===")
print(f"curr_lasti=16: curr_opcode={instr_map.get(16)}, prev_opcode={instr_map.get(14)}")
result = _detect_branch(16, 3, instr_map, {})
print(f"Result: {result}")

print()
print("=== Simulating else-branch detection ===")
print(f"curr_lasti=22: curr_opcode={instr_map.get(22)}, prev_opcode={instr_map.get(20)}")
result2 = _detect_branch(22, 5, instr_map, {})
print(f"Result: {result2}")

# Full trace
print()
print("=== Full trace ===")
r = run_trace(code)
for s in r["steps"]:
    print(f"line={s['line_number']} opcode={s['opcode']} branches={s['branches_taken']}")
