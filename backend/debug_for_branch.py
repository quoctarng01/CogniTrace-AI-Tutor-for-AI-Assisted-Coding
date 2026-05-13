import sys
sys.path.insert(0, ".")

from tracer.tracer import run_trace, _build_instr_map, _get_prev_bytecode_opcode, _detect_branch_for_step

code = """
total = 0
for i in range(3):
    total += i
"""

compiled = compile(code, "<test>", "exec")
instr_map = _build_instr_map(compiled)

# Simulate the events we know:
# line=3, curr=22(FOR_ITER), prev=20(GET_ITER)  <-- should fire for loop detection
# line=4, curr=28(LOAD_NAME), prev=26(STORE_NAME)

loop_iterations = {}

print("Simulating FOR_ITER detection (curr_lasti=22, line=3):")
result = _detect_branch_for_step(22, 3, instr_map, loop_iterations)
print(f"  Result: {result}")

print()
print("Simulating body step (curr_lasti=28, line=4):")
result2 = _detect_branch_for_step(28, 4, instr_map, loop_iterations)
print(f"  Result: {result2}")

# Check instr_map
print()
print("Key offsets in instr_map:")
for off in [20, 22, 26, 28]:
    print(f"  offset {off}: {instr_map.get(off)}")
