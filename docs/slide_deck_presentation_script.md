# CogniTrace — Thesis Progress Presentation Script

This document provides a slide-by-slide structure, visual layout, and speaking script for your progress presentation. It consists of **12 structured slides** designed to show your supervisor both high-level academic motivation, current project timeline health, deep-dive engineering details, and ongoing challenges.

---

## Slide 1: Title Slide (Project Overview)
### 📺 Visual Content
*   **Title**: CogniTrace: Interactive Program Visualization and AI-Assisted Tutoring for Python
*   **Subtitle**: Thesis Progress Report & System Architecture Demonstration
*   **Presenter Name**: [Your Name]
*   **Supervisor Name**: [Supervisor's Name]
*   **Key Tech Badges**: FastAPI, React/Next.js, `sys.settrace()`, LLM Streaming (SSE), Spaced Repetition (SM-2)

### 🗣️ What to Say (Speaking Notes)
> "Good morning/afternoon, Professor. Today I am presenting the progress report for my thesis project, CogniTrace. 
> 
> CogniTrace is an educational platform designed to bridge the gap between dynamic code execution states and cognitive understanding. Students today frequently use AI-assisted tools like Github Copilot or ChatGPT to generate code, but they often struggle to understand *how* that code executes or *why* it fails. 
> 
> In this presentation, I will cover the core challenges we are solving, outline my progress against our original project timeline, show the underlying 4-phase system architecture, discuss our major engineering breakthroughs, and demonstrate a working live prototype."

---

## Slide 2: Motivation & Problem Statement
### 📺 Visual Content
*   **Problem 1: The AI Copy-Paste Habit**: Novices execute AI-generated code without building a mental model of execution control flow.
*   **Problem 2: Debugger Complexity**: Professional debuggers (VS Code, pdb) expose excessive call-stack noise instead of educational value.
*   **Problem 3: Context-Agnostic LLM Answers**: General chat interfaces describe code statically; they don't know the exact runtime values of the user's execution frames.
*   **Solution**: An interactive environment that isolates execution, tracks runtime state, streams grounded AI explanations, and schedules reviews for retention.

### 🗣️ What to Say (Speaking Notes)
> "Let's begin with why this tool is necessary. With the rise of AI coding assistants, students can write complex scripts with a single prompt. However, they lack the program visualization skills needed to debug and learn from this code. 
> 
> Traditional debuggers are built for production developers, exposing complex system details that overwhelm beginners. At the same time, asking ChatGPT 'why is my code failing?' yields static explanations that don't account for the actual variables in memory. 
> 
> CogniTrace solves this by combining AST static analysis, dynamic tracing in a secure sandbox, and context-grounded AI explanation streaming to guide the student step-by-step."

---

## Slide 3: Project Timeline & Milestone Progress
### 📺 Visual Content
*   **Thesis Gantt Chart / Roadmap Visual**:
    *   **Phase 0: Static Analysis (AST)**: 100% Completed ✅
    *   **Phase 1: Subprocess Execution Tracer**: 100% Completed ✅
    *   **Phase 2: LLM Caching & Router**: 90% Completed (In Integration Testing) 🟡
    *   **Phase 3: SM-2 Review Queue**: 75% Completed (UI Tuning) 🟡
    *   **Phase 4: User Evaluation Study**: Scheduled for Next Month 📅
*   **Current Progress Health**: 
    *   Development is running on schedule.
    *   Core features implemented; currently addressing boundary conditions and optimization.

### 🗣️ What to Say (Speaking Notes)
> "Before we dive into the technical details, I want to present where we stand against our original project timeline.
> 
> To date, we have fully completed the static analysis and dynamic execution tracing backends. The AI streaming router and caching system are at 90% completion, with integration testing currently underway. We have also completed the core mathematical logic for the spaced repetition review queue, and we are now tuning the React interface.
> 
> Overall, we are on track to begin our user evaluation study next month, as originally scheduled."

---

## Slide 4: The 4-Phase System Pipeline
### 📺 Visual Content
*   *Include the pipeline architecture flowchart here:*
```
[User Code Input] 
       │
       ▼
[Phase 0: AST Static Analysis] (Security & Anti-Pattern checks)
       │
       ▼
[Phase 1: Dynamic Execution Tracer] (Isolated sys.settrace() subprocess)
       │
       ▼
[Phase 2: LLM Explanation Engine] (Real-time SSE Explanations & Caching)
       │
       ▼
[Phase 3: Spaced Repetition Queue] (SM-2 review challenges)
```

### 🗣️ What to Say (Speaking Notes)
> "Here is our core system architecture, designed as a strict unidirectional pipeline. 
> 
> When the user inputs code, it passes through **Phase 0** where we parse the Abstract Syntax Tree for security and common bugs. If clean, it flows to **Phase 1**, running in an isolated subprocess under `sys.settrace()` to gather execution frames. 
> 
> In **Phase 2**, the tracer's output is sent to our LLM engine to stream step-by-step explanations back to the client via Server-Sent Events. Finally, in **Phase 3**, difficult concepts are turned into flashcards scheduled via the SuperMemo-2 algorithm for long-term review. Let’s look at how each phase is engineered."

---

## Slide 5: Phase 0 & 1: AST Validation & Subprocess Sandboxing
### 📺 Visual Content
*   **Static AST Guards ([static_analysis.py](file:///c:/Users/quoct/codescope/backend/analyzers/static_analysis.py))**:
    *   Blocked Modules: `os`, `sys`, `subprocess`, `requests`, `socket`.
    *   Rule Checks: `missing_none_guard` (TypeError risks), `mutable_default` (`def f(x=[])`).
*   **Dynamic Sandbox Boundaries ([runner.py](file:///c:/Users/quoct/codescope/backend/runner.py))**:
    *   Isolation: Code runs in a clean `subprocess.Popen` shell.
    *   OS Limits: `resource.setrlimit(RLIMIT_AS, 256MB)` (RAM), `RLIMIT_CPU = 4s` (CPU time limit).
    *   Timeout protection (5 seconds execution ceiling).

### 🗣️ What to Say (Speaking Notes)
> "Running user-submitted code on a backend server introduces major security risks. To solve this, we implemented two-tier sandboxing. 
> 
> First is **Static Validation** using an AST visitor. Before compilation, we block malicious imports, system builtins like `open()`, and dunder attribute access. We also analyze the AST to detect logic bugs such as missing None guards and mutable default argument states.
> 
> If static checks pass, the code is written to a temporary file and executed in a separate **Subprocess Sandbox**. We set strict OS kernel resource limits using `setrlimit` to bound execution memory to 256 Megabytes and CPU time to 4 seconds, neutralizing infinite loops or memory bombs."

---

## Slide 6: Advanced Control Flow: Branch Evaluation & Tutor Checkpoints
### 📺 Visual Content
*   **Opcode-Level Inspection**: Maps execution offset to compiler instructions using the `dis` module.
*   **Branch Evaluation**: Evaluates condition parameters (`taken = True / False` on `if` structures) and short-circuits (`and` / `or`).
*   **Tutor Checkpoints ([tracer.py](file:///c:/Users/quoct/codescope/backend/tracer/tracer.py))**:
    *   Generates interactive prediction challenges in real-time.
    *   Types: `variable_prediction`, `branch_prediction`, `exception_prediction`.

### 🗣️ What to Say (Speaking Notes)
> "CogniTrace does not just report which line executed. To help students understand logical decisions, we analyze CPython bytecode using the `dis` module to identify branches. 
> 
> When the tracer hits a conditional node, it evaluates the condition in the runtime namespace to detect which branch will be taken, or if a logical operator short-circuited. 
> 
> Using this data, CogniTrace dynamically injects **Tutor Checkpoints**. These are multiple-choice questions that interrupt execution, asking the student to predict a variable's next value or whether a branch will fire, converting passive observation into active learning."

---

## Slide 7: Phase 2: Grounded AI Caching & Falling-Back Router
### 📺 Visual Content
*   **Real-time Streaming**: Server-Sent Events (SSE) stream character tokens dynamically for seamless reading.
*   **Three-Tier Routing**: 
    1. Ollama Cloud (Fast, Primary)
    2. Local Ollama (Local fallback)
    3. OpenAI/Claude (Public fallback API)
*   **Content-Addressed Cache**:
    *   Key: `SHA-256(code + line_number + variable_state)`
    *   Avoids querying LLMs for already-analyzed states $\rightarrow$ reduces response latency to <10ms for cached hits.

### 🗣️ What to Say (Speaking Notes)
> "In Phase 2, we stream explanations using Server-Sent Events. To ensure cost-efficiency and high performance, we designed two key systems:
> 
> First is a **Three-Tier AI Router** that attempts to request Ollama Cloud, falls back to a locally hosted Ollama instance if offline, and uses commercial APIs like OpenAI or Claude as a final fallback.
> 
> Second is our **Content-Addressed Caching**. Since code execution often hits the same line with the same variables (e.g. inside a loop), we hash the code, active line, and variable state. If matched, we instantly return the explanation from Redis, eliminating API latency and token costs entirely."

---

## Slide 8: Phase 3: Active Recall & Spaced Repetition
### 📺 Visual Content
*   **Educational Concept**: Combats the *Ebbinghaus Forgetting Curve* using active recall.
*   **SM-2 Scheduling Equations**:
    *   $EF_{new} = EF_{old} + (0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$
    *   Interval ($I$) logic for rating $q$:
        *   If $q < 2$ (Again/Fail): $I=1, n=0$
        *   If $q = 2$ (Hard/Soft-Fail): $n = n \div 2, I = I \times 0.5$ *(Custom recovery)*
        *   If $q \ge 3$ (Success): $I_{1}=1, I_{2}=6, I_{n} = I_{n-1} \times EF$
*   **Active Recall Interface**: Student evaluates code-repair challenges directly in the review deck.

### 🗣️ What to Say (Speaking Notes)
> "Phase 3 implements the SuperMemo-2 algorithm to schedule review cards. Rather than simple flashcards, CogniTrace generates active recall cards based on the trace concepts students struggled with. 
> 
> The mathematics of the SM-2 algorithm calculate the next review interval based on user response quality from 0 to 5. 
> 
> We introduced a custom **Soft-Fail** mechanism for the 'Hard' rating. Standard SM-2 resets intervals completely on any incorrect answer. Our custom algorithm halves the interval and repetitions instead, reducing student frustration while keeping cards in the active review pool."

---

## Slide 9: Implementation & Testing Verification Matrix
### 📺 Visual Content
*   **Backend Testing Suite (`pytest`)**:
    *   `test_sandbox_bypass`: Validates security barriers.
    *   `test_branch_detection`: Verifies byte offsets.
    *   `test_sm2`: Confirms scheduling math.
    *   **Result**: 280/280 tests passed.
*   **Frontend Testing Suite (`Vitest`)**:
    *   Unit asserts for UI panels: `VariablePanel`, `TutorChallenge`, `AnimationControls`.
    *   **Result**: 41/41 tests passed.
*   **End-to-End Suite (`Playwright`)**:
    *   Interactive trace simulation and complete review cards flow.

### 🗣️ What to Say (Speaking Notes)
> "Before running the live demo, I want to highlight the engineering stability of the platform. We built a comprehensive, automated testing matrix. 
> 
> On the backend, we run **280 pytest cases** verifying sandbox security, bytecode offsets, and scheduler math. 
> 
> On the frontend, we use **Vitest for 41 unit tests** checking UI reactivity, alongside **Playwright for end-to-end integration flows**. All tests are passing successfully, confirming system reliability."

---

## Slide 10: Live System Demonstration (Demo Walkthrough)
### 📺 Visual Content
*   **Interactive Workbench Walkthrough**:
    1.  *Static Security Guard*: Submitting `import os` $\rightarrow$ AST validation rejects instantly.
    2.  *Tracing sum_evens*: Input a loop code snippet $\rightarrow$ trace step-by-step.
    3.  *Branch visual & variable trace*: Green highlights on variable mutations.
    4.  *Tutor Challenge*: Answering an inline checkpoint.
    5.  *What-If Sandbox*: Editing input list $\rightarrow$ replaying trace.
    6.  *Spaced Repetition Review*: Rating review cards to update queue.

### 🗣️ What to Say (Speaking Notes)
> *"I will now present a live demonstration of the system in action.*
> 
> *[Action: Open http://localhost:3000/tracer]*
> 
> *First, we submit an unauthorized import to show the AST block. You can see it is intercepted before execution.*
> 
> *Next, we execute our sum_evens loop. As we click 'Step Forward', the execution cursor advances, and our variable panel highlights modified states in green.*
> 
> *Here, the program halts on a Tutor Challenge, asking us to predict the branch choice. We answer it, and it gives immediate feedback.*
> 
> *Finally, we click the 'What If?' button, change the input array variables, and replay execution from step zero to see how the control flow shifts. We can flag this card for review and rate it in our deck."*

---

## Slide 11: Current Technical Challenges & Blocker Issues
### 📺 Visual Content
*   **Challenge 1: Heap & Reference Visualizations**: Primitive variables are easily mapped, but complex objects (mutable nested lists, dictionary references) are harder to graph dynamically.
*   **Challenge 2: Subprocess Sandbox Latency Overhead**: Launching a new `subprocess.Popen` on every user execution yields a 150ms startup delay. Investigating pre-warmed subprocess pools.
*   **Challenge 3: Prompt Grounding & LLM Hallucinations**: Standard LLM prompts sometimes output generalized descriptions rather than referencing the specific, actual runtime variable values in the trace payload.

### 🗣️ What to Say (Speaking Notes)
> "While our core features are stable, we are currently navigating three technical challenges.
> 
> First, visualizing nested data structures in the frontend is complex. Mapping reference pointers in Python's memory model to a simple UI node graph requires careful AST-to-graph translation.
> 
> Second, spawning a new shell process for every code execution ensures security, but creates minor startup latency. We are exploring pre-warmed process pools to lower latency.
> 
> Third, ensuring the LLM refers *strictly* to the live variable namespace in the prompt, rather than hallucinating generic logic explanations, is an ongoing prompt engineering and parameter tuning effort."

---

## Slide 12: Future Roadmap & Discussion Points
### 📺 Visual Content
*   **Future Milestones**:
    *   Multi-file trace execution in the isolated sandbox.
    *   Algorithmic complexity ($O(N)$ vs $O(N^2)$) static checks.
*   **Discussion & Feedback Questions**:
    1.  *Evaluation Method*: What metrics (e.g., error rates, code repair speed) should we measure in the user study?
    2.  *Sandbox Scope*: Should we support common scientific libraries like `numpy` or `pandas`, or restrict strictly to builtins?
    3.  *Offline Deployment*: Should local Ollama support be a core focus, or should we assume a cloud API connection for standard users?

### 🗣️ What to Say (Speaking Notes)
> "Looking ahead, our final phase milestones include multi-file import tracing and algorithmic complexity checks.
> 
> To conclude my presentation, Professor, I would love to hear your feedback on three key issues:
> 
> First, the design of our user study—specifically what learning metrics you think we should focus on measuring. Second, whether we should expand the sandbox to allow scientific packages like numpy. And third, whether we should focus on tuning local Ollama deployments or rely on cloud APIs.
> 
> Thank you, and I look forward to your suggestions."
