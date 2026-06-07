'use client';

import React, { useState, useMemo, useEffect } from 'react';
import type { TraceStep } from '@/types/trace';
import styles from './TraceTreePanel.module.css';

interface TreeNode {
  id: string;
  type: 'root' | 'call' | 'loop' | 'iteration' | 'step';
  name: string;
  startStep: number;
  endStep: number;
  children: TreeNode[];
  callDepth?: number;
  lineNumber?: number;
  lineContent?: string;
}

interface TraceTreePanelProps {
  steps: TraceStep[];
  currentStep: number;
  onSelectStep: (stepNumber: number) => void;
  code: string;
}

export function TraceTreePanel({ steps, currentStep, onSelectStep, code }: TraceTreePanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Parse tree on load/change
  const treeRoot = useMemo(() => {
    return buildExecutionTree(steps, code);
  }, [steps, code]);

  // Auto-expand nodes that contain the active step
  useEffect(() => {
    if (!treeRoot) return;
    const toExpand: Record<string, boolean> = { ...expanded };
    
    function autoExpand(node: TreeNode) {
      if (currentStep >= node.startStep && currentStep <= node.endStep) {
        if (node.children.length > 0 && node.type !== 'step') {
          toExpand[node.id] = true;
          node.children.forEach(autoExpand);
        }
      }
    }
    autoExpand(treeRoot);
    setExpanded(toExpand);
  }, [currentStep, treeRoot]);

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Render nodes recursively
  const renderNode = (node: TreeNode, depth: number = 0): React.ReactNode => {
    const hasChildren = node.children.length > 0;
    const isExpanded = expanded[node.id] ?? false;
    const isActive = currentStep >= node.startStep && currentStep <= node.endStep;
    const isCurrentExactStep = node.type === 'step' && node.startStep === currentStep;

    let icon = '▶';
    if (node.type === 'call') icon = '📦';
    else if (node.type === 'loop') icon = '🔁';
    else if (node.type === 'iteration') icon = '◽';
    else if (node.type === 'root') icon = '⚡';

    if (node.type === 'root') {
      // Don't render the root node shell itself, just its children
      return <>{node.children.map((child) => renderNode(child, depth))}</>;
    }

    return (
      <div key={node.id} className={styles.treeNodeWrapper}>
        <div
          className={`${styles.treeNode} ${isActive ? styles.active : ''} ${
            isCurrentExactStep ? styles.exactMatch : ''
          }`}
          style={{ paddingLeft: `${depth * 14}px` }}
          onClick={() => onSelectStep(node.startStep)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => toggleExpand(node.id, e)}
              className={styles.expandBtn}
            >
              {isExpanded ? '▼' : '►'}
            </button>
          ) : (
            <span className={styles.indentDot}></span>
          )}
          
          <span className={styles.nodeIcon}>{icon}</span>
          <span className={styles.nodeName} title={node.name}>
            {node.name}
          </span>
          <span className={styles.stepRange}>
            {node.startStep === node.endStep ? `#${node.startStep + 1}` : `${node.startStep + 1}-${node.endStep + 1}`}
          </span>
        </div>
        
        {hasChildren && isExpanded && (
          <div className={styles.nodeChildren}>
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Execution Outline</h3>
      </div>
      <div className={styles.treeList}>
        {treeRoot && renderNode(treeRoot, 0)}
      </div>
    </div>
  );
}

// ── Parsing Tree Algorithm ───────────────────────────────────────

function buildExecutionTree(steps: TraceStep[], code: string): TreeNode {
  const lines = code.split('\n');
  const getLineContent = (lineNum: number) => {
    if (lineNum >= 1 && lineNum <= lines.length) {
      return (lines[lineNum - 1] ?? '').trim();
    }
    return '';
  };
  const isLoopLine = (lineNum: number) => {
    const content = getLineContent(lineNum);
    return content.startsWith('for ') || content.startsWith('while ');
  };

  interface TempNode {
    type: 'call' | 'step';
    stepNumber?: number;
    lineNumber?: number;
    depth: number;
    children: TempNode[];
    startStep: number;
    endStep: number;
  }

  const root: TempNode = {
    type: 'call',
    depth: 1,
    children: [],
    startStep: 0,
    endStep: steps.length - 1,
  };

  const stack: TempNode[] = [root];

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (!step) continue;
    const depth = step.call_depth ?? 1;

    // Adjust stack to match current depth
    while (stack.length > 1 && (stack[stack.length - 1]?.depth ?? 0) > depth) {
      stack.pop();
    }

    const currentTop = stack[stack.length - 1];
    if (!currentTop) continue;

    if (depth > currentTop.depth) {
      // Create new call node
      const newCall: TempNode = {
        type: 'call',
        depth: depth,
        children: [],
        startStep: i,
        endStep: i,
      };
      currentTop.children.push(newCall);
      stack.push(newCall);
    }

    // Add step to current active node
    const currentActive = stack[stack.length - 1];
    if (!currentActive) continue;
    
    currentActive.children.push({
      type: 'step',
      stepNumber: step.step_number,
      lineNumber: step.line_number,
      depth: depth,
      children: [],
      startStep: i,
      endStep: i,
    });
    currentActive.endStep = i;
    
    // Update ancestor end steps
    for (let s = 0; s < stack.length - 1; s++) {
      const node = stack[s];
      if (node) {
        node.endStep = i;
      }
    }
  }

  function processNode(temp: TempNode): TreeNode {
    if (temp.type === 'step') {
      const stepIdx = temp.stepNumber!;
      const step = steps[stepIdx];
      if (!step) {
        return {
          id: `step-${stepIdx}`,
          type: 'step',
          name: `Step ${stepIdx + 1}`,
          startStep: stepIdx,
          endStep: stepIdx,
          children: [],
        };
      }
      const content = getLineContent(step.line_number);
      return {
        id: `step-${stepIdx}`,
        type: 'step',
        name: `L${step.line_number}: ${content.substring(0, 32)}`,
        startStep: stepIdx,
        endStep: stepIdx,
        lineNumber: step.line_number,
        lineContent: content,
        children: [],
      };
    }

    const processedChildren: TreeNode[] = [];
    let i = 0;
    while (i < temp.children.length) {
      const child = temp.children[i];
      if (!child) {
        i++;
        continue;
      }

      if (child.type === 'call') {
        processedChildren.push(processNode(child));
        i++;
        continue;
      }

      const stepIdx = child.stepNumber!;
      const step = steps[stepIdx];
      if (!step) {
        i++;
        continue;
      }
      
      if (isLoopLine(step.line_number)) {
        const loopLine = step.line_number;
        const loopContent = getLineContent(loopLine);
        const iterations: TreeNode[] = [];
        let currentIterationSteps: TreeNode[] = [];
        let iterStartStep = stepIdx;
        
        let j = i;
        while (j < temp.children.length) {
          const nextChild = temp.children[j];
          if (!nextChild) {
            j++;
            continue;
          }
          if (nextChild.type === 'call') {
            currentIterationSteps.push(processNode(nextChild));
            j++;
            continue;
          }
          
          const nextStepIdx = nextChild.stepNumber!;
          const nextStep = steps[nextStepIdx];
          if (!nextStep) {
            j++;
            continue;
          }
          
          if (nextStep.line_number === loopLine && currentIterationSteps.length > 0) {
            iterations.push({
              id: `loop-${loopLine}-iter-${iterations.length}-${stepIdx}`,
              type: 'iteration',
              name: `Iteration #${iterations.length + 1}`,
              startStep: iterStartStep,
              endStep: nextStepIdx - 1,
              children: currentIterationSteps,
            });
            currentIterationSteps = [];
            iterStartStep = nextStepIdx;
          }
          
          currentIterationSteps.push({
            id: `step-${nextStepIdx}`,
            type: 'step',
            name: `L${nextStep.line_number}: ${getLineContent(nextStep.line_number).substring(0, 32)}`,
            startStep: nextStepIdx,
            endStep: nextStepIdx,
            lineNumber: nextStep.line_number,
            lineContent: getLineContent(nextStep.line_number),
            children: [],
          });
          j++;
        }
        
        if (currentIterationSteps.length > 0 && j > 0) {
          const lastChild = temp.children[j - 1];
          if (lastChild) {
            const lastChildEndStep = lastChild.type === 'step' ? lastChild.stepNumber : lastChild.endStep;
            iterations.push({
              id: `loop-${loopLine}-iter-${iterations.length}-${stepIdx}`,
              type: 'iteration',
              name: `Iteration #${iterations.length + 1}`,
              startStep: iterStartStep,
              endStep: lastChildEndStep ?? iterStartStep,
              children: currentIterationSteps,
            });
          }
        }
        
        if (j > 0) {
          const lastChildNode = temp.children[j - 1];
          if (lastChildNode) {
            const lastChildNodeEndStep = lastChildNode.type === 'step' ? lastChildNode.stepNumber : lastChildNode.endStep;
            processedChildren.push({
              id: `loop-${loopLine}-${stepIdx}`,
              type: 'loop',
              name: `Loop (Line ${loopLine}): ${loopContent.substring(0, 24)}`,
              startStep: stepIdx,
              endStep: lastChildNodeEndStep ?? stepIdx,
              children: iterations,
            });
          }
        }
        
        i = j;
      } else {
        processedChildren.push(processNode(child));
        i++;
      }
    }

    let nodeName = 'Main Code';
    if (temp.depth > 1) {
      const startStep = steps[temp.startStep];
      if (startStep) {
        const funcName = getLineContent(startStep.line_number);
        nodeName = `Frame Depth ${temp.depth}: ${funcName.substring(0, 24)}`;
      }
    }

    return {
      id: `call-depth-${temp.depth}-${temp.startStep}`,
      type: temp.depth === 1 ? 'root' : 'call',
      name: nodeName,
      startStep: temp.startStep,
      endStep: temp.endStep,
      children: processedChildren,
      callDepth: temp.depth,
    };
  }

  return processNode(root);
}
