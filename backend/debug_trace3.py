import dis, ast

code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2
"""

compiled = compile(code.strip(), "<test>", "exec")

print("=== Offset -> line (co_positions) ===")
for instr in dis.get_instructions(compiled):
    try:
        pos = instr.positions()
        line = pos.lineno if pos.lineno is not None else "None"
        print(f"  {instr.offset:3d}: {instr.opname:<30} line={line}")
    except Exception as e:
        print(f"  {instr.offset:3d}: {instr.opname:<30} error={e}")

print()
print("=== Scan test: line 3 ===")
from tracer.tracer import _build_instr_map, _build_offset_to_line_map

instr_map = _build_instr_map(compiled)
offset_to_line = _build_offset_to_line_map(compiled)

print("instr_map:", dict(instr_map))
print("offset_to_line:", dict(offset_to_line))

# curr_lasti for line 3 would be 16 (the first if-body instruction)
# prev_lasti would be 14 (POP_JUMP_IF_FALSE at offset 14)
print()
print("Testing line 3 with curr_lasti=16:")
from tracer.tracer import _find_all_instrs_on_line
instrs = _find_all_instrs_on_line(16, 3, instr_map, offset_to_line)
print("All instrs on line 3:", instrs)
