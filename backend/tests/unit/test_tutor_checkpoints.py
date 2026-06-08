import pytest
from tracer.tracer import generate_tutor_checkpoints

def test_no_checkpoints_for_empty_steps():
    assert generate_tutor_checkpoints([], "x = 1") == []

def test_branch_checkpoint_detection():
    steps = [
        {
            "step_number": 0,
            "line_number": 1,
            "bytecode_offset": 0,
            "opcode": "LOAD_CONST",
            "variables": {"x": {"type": "int", "value": "5", "changed": False}},
            "branches_taken": {},
        },
        {
            "step_number": 1,
            "line_number": 2,
            "bytecode_offset": 2,
            "opcode": "POP_JUMP_IF_FALSE",
            "variables": {"x": {"type": "int", "value": "5", "changed": False}},
            "branches_taken": {
                "if": {
                    "taken": True,
                    "line": 2,
                    "branch": "then",
                    "condition": "x > 3"
                }
            },
        },
        {
            "step_number": 2,
            "line_number": 3,
            "bytecode_offset": 4,
            "opcode": "LOAD_CONST",
            "variables": {"x": {"type": "int", "value": "5", "changed": False}},
            "branches_taken": {},
        }
    ]
    checkpoints = generate_tutor_checkpoints(steps, "x = 5\nif x > 3:\n    pass")
    assert len(checkpoints) == 1
    cp = checkpoints[0]
    assert cp["checkpoint_type"] == "branch_prediction"
    assert cp["step_number"] == 1
    assert cp["line_number"] == 2
    assert cp["correct_value"] == "True (enter the branch block)"
    assert "True (enter the branch block)" in cp["options"]

def test_variable_mutation_checkpoint_detection():
    steps = [
        {
            "step_number": 0,
            "line_number": 1,
            "bytecode_offset": 0,
            "opcode": "LOAD_CONST",
            "variables": {"x": {"type": "int", "value": "5", "changed": False}},
            "branches_taken": {},
        },
        {
            "step_number": 1,
            "line_number": 2,
            "bytecode_offset": 2,
            "opcode": "STORE_FAST",
            "variables": {"x": {"type": "int", "value": "10", "changed": True}},
            "branches_taken": {},
        }
    ]
    checkpoints = generate_tutor_checkpoints(steps, "x = 5\nx = 10")
    assert len(checkpoints) == 1
    cp = checkpoints[0]
    assert cp["checkpoint_type"] == "variable_prediction"
    assert cp["step_number"] == 0
    assert cp["line_number"] == 1
    assert cp["correct_value"] == "10"
    assert "5" in cp["options"]
    assert "10" in cp["options"]

def test_exception_checkpoint_detection():
    steps = [
        {
            "step_number": 0,
            "line_number": 1,
            "bytecode_offset": 0,
            "opcode": "LOAD_CONST",
            "variables": {},
            "branches_taken": {},
        },
        {
            "step_number": 1,
            "line_number": 2,
            "bytecode_offset": 2,
            "opcode": "EXCEPTION",
            "variables": {},
            "branches_taken": {},
            "exception_info": "ZeroDivisionError: division by zero"
        }
    ]
    checkpoints = generate_tutor_checkpoints(steps, "x = 1 / 0")
    assert len(checkpoints) == 1
    cp = checkpoints[0]
    assert cp["checkpoint_type"] == "exception_prediction"
    assert cp["step_number"] == 0
    assert cp["line_number"] == 1
    assert cp["correct_value"] == "Yes, it will raise ZeroDivisionError."
