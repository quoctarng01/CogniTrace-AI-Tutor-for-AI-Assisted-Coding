# THESIS-01: Study Protocol and IRB Documentation

> **Source:** Extracted from `IMPLEMENTATION_PLAN.md` — moved here because IRB forms and study protocols are ethics/legal documents, not implementation tasks.

**Status:** These are reference documents for the CodeScope thesis project. They are NOT implementation tasks for the engineering team. The implementation plan at `c:/Users/quoct/codescope/IMPLEMENTATION_PLAN.md` covers only the engineering fixes.

---

## Files to create (in `c:/Users/quoct/codescope/docs/`)

- `study-protocol.md` — full study methodology
- `consent-form.md` — participant consent template
- `irb-application.md` — IRB submission outline

---

## Study Protocol

**Study Title:** CodeScope: AI-Powered Python Code Tracing for CS Education — A Mixed-Methods Study on Comprehension and Retention

### Background
[Describe the problem: students struggle to understand AI-generated code]

### Objectives
1. Primary: Measure whether CodeScope improves comprehension of Python code snippets
2. Secondary: Evaluate whether spaced repetition via CodeScope cards improves long-term retention

### Methods

**Participants:**
- Target: N=40 CS students (20 treatment, 20 control)
- Recruitment: University CS courses
- Inclusion: Python programming experience (at least one course)

**Procedure:**
1. Pre-test: Baseline Python comprehension quiz (10 questions)
2. Intervention (treatment group): Use CodeScope tracer + review cards for 4 weeks
3. Control group: Standard study methods
4. Post-test: Same quiz + subjective comprehension survey
5. 4-week follow-up: Retention test

**Measures:**
- Comprehension quiz scores (primary outcome)
- SUS score (System Usability Scale)
- Time-on-task metrics (from CodeScope analytics)
- Semi-structured interviews (N=10)

### Risks and Benefits
- Risk: Minimal — educational software, no sensitive data collected beyond anonymized usage logs
- Benefit: Participants may improve Python skills; results contribute to educational research

### Data Handling
- All data anonymized (user IDs replaced with study IDs)
- Usage logs stored in Supabase with RLS
- Interview recordings transcribed and anonymized before analysis
- Raw data deleted after 3 years

### Ethics
This study will be submitted for IRB review. Participants must provide informed consent.

---

## Consent Form Template

# Informed Consent Form

## Study: CodeScope — AI-Powered Python Code Tracing

**Principal Investigator:** [Your Name]
**Institution:** [Your Institution]

### What is this study about?
You are invited to participate in a research study about an educational tool called CodeScope that helps students understand and retain Python code. This form gives you information about the study to help you decide if you want to participate.

### What will I do?
- Complete a pre-test quiz about Python (15 minutes)
- Use CodeScope for 4 weeks (approximately 30 minutes per week)
- Complete a post-test quiz (15 minutes)
- Optionally, participate in a 30-minute interview about your experience

### Risks
- This study involves minimal risk. The main risk is that you may feel some frustration while using the software.

### Benefits
- You may improve your Python skills through regular practice.
- Your feedback will help improve the tool for future students.

### Privacy
- Your data will be anonymized (we replace your name with a study ID).
- Usage logs (which code snippets you traced, when you reviewed cards) will be collected.
- Interview recordings will be transcribed and then deleted.
- We will never share your identity with third parties.

### Voluntary Participation
- Participation is completely voluntary.
- You can withdraw at any time without penalty.
- You can skip any quiz question or interview question you don't want to answer.

### Contact
If you have questions about the study, contact [PI email].

If you have questions about your rights as a research participant, contact [IRB office email].

---

**I have read this form and understand it. I agree to participate.**

Name: _________________________

Date: _________________________

Signature: _________________________

---

## IRB Application Outline

**Form:** Exempt Review (Category 1) — Education research with normal educational practices.

### Study Description
[Expand study-protocol.md here]

### Procedures
[Detailed step-by-step procedures]

### Risks
- Risk of breach of confidentiality: mitigated by anonymization
- Risk of emotional distress: minimal
- Overall risk level: **Minimal**

### Protections
- Anonymization of all user data
- No collection of PII beyond consent form
- Consent form stored separately from study data
- Right to withdraw at any time

### Recruitment
- Flyers in CS department
- Announcements in Canvas/Piazza
- No coercion, no course credit for participation
