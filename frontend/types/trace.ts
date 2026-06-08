/**
 * TraceStep and related types for the frontend.
 */

export interface VariableInfo {
  type: string;
  value: string;
  changed: boolean;
}

export interface BranchInfo {
  type: 'if' | 'for' | 'while' | 'ternary' | 'and_or' | 'bool_op' | string;
  taken?: boolean;
  line?: number;
  iteration?: number;
  [key: string]: unknown;
}

export interface TraceStep {
  step_number: number;
  line_number: number;
  bytecode_offset: number;
  opcode: string;
  variables: Record<string, VariableInfo>;
  call_depth: number;
  branches_taken: Record<string, unknown>;
  duration_ms: number;
  return_value?: string;
  exception_info?: string;
}

export interface TraceCheckpoint {
  step_number: number;
  line_number: number;
  checkpoint_type: 'branch_prediction' | 'variable_prediction' | 'exception_prediction';
  prompt: string;
  options: string[];
  correct_value: string;
  variable_name: string | null;
  meta: Record<string, any>;
}

export interface TraceResult {
  trace_id: string;
  steps: TraceStep[];
  total_steps: number;
  duration_ms: number;
  error?: string;
  error_message?: string;
  checkpoints?: TraceCheckpoint[];
}

// Type badge colors
export const TYPE_COLORS: Record<string, string> = {
  int: '#3b82f6', // blue
  float: '#06b6d4', // cyan
  str: '#22c55e', // green
  bool: '#f59e0b', // amber
  list: '#a855f7', // purple
  tuple: '#8b5cf6', // violet
  dict: '#f97316', // orange
  set: '#ec4899', // pink
  NoneType: '#6b7280', // gray
  function: '#64748b', // slate
  type: '#475569', // dark slate
  module: '#94a3b8', // light slate
  object: '#71717a', // zinc
};

export function getTypeColor(typeName: string): string {
  return TYPE_COLORS[typeName] ?? '#71717a';
}
