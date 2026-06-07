"""Trace data models."""
from dataclasses import dataclass
from typing import Optional


class SandboxError(Exception):
    """Raised when user code contains a blocked side-effect pattern."""

    def __init__(self, pattern: str = ""):
        self.pattern = pattern
        super().__init__(f"Blocked operation: {pattern}")


@dataclass
class VariableInfo:
    """A variable's state at a specific trace step."""
    type: str          # type(val).__name__
    value: str         # repr(val)[:200]
    changed: bool      # true if value changed from previous step


@dataclass
class BranchInfo:
    """A branch taken during control flow."""
    branch_type: str   # 'if' | 'for' | 'while' | 'ternary' | 'and_or'
    taken: Optional[bool]  # True = if branch, False = else branch
    line: int
    iteration: int = 0      # 0 = not a loop


@dataclass
class TraceStep:
    """One step in the execution trace."""
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict[str, VariableInfo]
    branches_taken: dict
    duration_ms: float
    call_depth: int = 1
    exception_info: Optional[str] = None


@dataclass
class TraceResult:
    """Successful trace result."""
    steps: list[TraceStep]
    total_steps: int
    duration_ms: float


@dataclass
class TraceError:
    """Failed trace result."""
    error: str        # 'SYNTAX_ERROR' | 'TIMEOUT' | 'MAX_STEPS' | 'EXECUTION_ERROR'
    message: str
    line: Optional[int] = None
