# backend/api/routes.py
from fastapi import APIRouter
from pydantic import BaseModel

from backend.analyzers.static_analysis import analyze_code

router = APIRouter()


class AnalyzeRequest(BaseModel):
    code: str


class AnnotationSchema(BaseModel):
    line: int
    severity: str
    pattern_id: str
    message: str
    suggestion: str


class AnalyzeResponse(BaseModel):
    annotations: list[AnnotationSchema]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze Python source code for common AI-generated bug patterns.

    Returns annotations for:
      - Missing None guards (TypeError risk)
      - Mutable default arguments (shared state bug)
      - List comprehension aggressive filters (silent empty result)
      - Implicit truthiness checks (wrong truthy/falsy behavior)
      - requests calls without timeout (hang risk)
    """
    annotations = analyze_code(request.code)
    return AnalyzeResponse(
        annotations=[
            AnnotationSchema(
                line=ann.line,
                severity=ann.severity,
                pattern_id=ann.pattern_id,
                message=ann.message,
                suggestion=ann.suggestion,
            )
            for ann in annotations
        ]
    )
