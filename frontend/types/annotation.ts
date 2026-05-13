/**
 * Static analysis annotation types — mirrors backend/app/routers/static_analysis.py.
 */

export type AnnotationSeverity = "high" | "medium" | "low";

export interface Annotation {
  line: number;
  severity: AnnotationSeverity;
  pattern_id: string;
  message: string;
  suggestion: string;
}

export interface AnalyzeResponse {
  annotations: Annotation[];
}
