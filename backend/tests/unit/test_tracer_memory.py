"""Unit tests for tracer memory graph representation."""
import pytest
from tracer.tracer import run_trace


def test_tracer_captures_object_ids_and_heap_references():
    code = """
a = [10, 20, 30]
b = a
c = 42
d = {"x": 1, "y": 2}
"""
    res = run_trace(code)
    assert "steps" in res
    steps = res["steps"]
    assert len(steps) > 0

    last_step = steps[-1]
    vars_map = last_step["variables"]

    assert "a" in vars_map
    assert "b" in vars_map
    assert "c" in vars_map
    assert "d" in vars_map

    # List reference check
    assert vars_map["a"]["is_ref"] is True
    assert vars_map["a"]["type"] == "list"
    assert vars_map["a"]["id"] is not None

    # Aliasing check: b = a
    assert vars_map["b"]["id"] == vars_map["a"]["id"]

    # Primitive check: c = 42
    assert vars_map["c"]["is_ref"] is False
    assert vars_map["c"]["type"] == "int"

    # Dict reference check & children
    assert vars_map["d"]["is_ref"] is True
    assert vars_map["d"]["children"]["kind"] == "mapping"
    assert len(vars_map["d"]["children"]["pairs"]) == 2


def test_tracer_mutation_tracking():
    code = """
items = [1, 2]
items.append(3)
items = [10, 20]
"""
    res = run_trace(code)
    steps = res["steps"]

    # Step 0 / 1: items created
    items_step1 = None
    items_step2 = None
    items_step3 = None

    for s in steps:
        if "items" in s["variables"]:
            v = s["variables"]["items"]
            if v["value"] == "[1, 2]" and not items_step1:
                items_step1 = v
            elif v["value"] == "[1, 2, 3]" and not items_step2:
                items_step2 = v
            elif v["value"] == "[10, 20]" and not items_step3:
                items_step3 = v

    assert items_step1 is not None
    assert items_step2 is not None
    assert items_step3 is not None

    # Step 2: mutated in place (same ID, changed value)
    assert items_step2["mutation_type"] == "mutated"
    assert items_step2["id"] == items_step1["id"]

    # Step 3: reassigned to a new list object (different ID)
    assert items_step3["mutation_type"] == "reassigned"
    assert items_step3["id"] != items_step1["id"]
