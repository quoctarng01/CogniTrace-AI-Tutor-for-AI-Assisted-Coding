"""
LLM Router — GitHub Models only.

Key design:
  - GitHub Models (models.github.ai) is the ONLY provider — uses your GitHub PAT.
  - Explanations are cached by SHA-256 before any API call is made.
"""
from __future__ import annotations

import json
import hashlib
import logging
from typing import Any, AsyncGenerator, Optional
from dataclasses import dataclass
from enum import Enum

import httpx

from app.config import settings

logger = logging.getLogger("codescope.llm_router")

# ── Types ──────────────────────────────────────────────────────────

class LLMProvider(Enum):
    OLLAMA_CLOUD = "ollama_cloud"
    GITHUB_MODELS = "github_models"

@dataclass
class LLMResponse:
    provider: LLMProvider
    model_name: str
    text: str
    cached: bool = False
    duration_ms: float = 0.0

# ── Prompts ───────────────────────────────────────────────────────

# System message: fixed instructions for every request.
# Does NOT contain runtime data — that goes in the user message.
SYSTEM_PROMPT = """You are a Python code educator. Your job is to explain \
WHY a specific line of code is executing, given the current runtime context.

Instructions:
- Explain WHY this specific line is necessary given the current variable state.
- Do NOT explain what the code does generally — explain the specific execution reason.
- Be concise: 2-3 sentences maximum.
- Include a brief inline code example only if it meaningfully clarifies the explanation.
- If the line involves a branch decision (if/else), state which branch was taken and why.
- If the line is in a loop, mention the current iteration context."""

# User message template: filled with runtime data per request.
# Kept separate from the system message so context tokens scale cleanly.
USER_PROMPT_TEMPLATE = """\
Code being traced:
```python
{code}
```

Currently executing line {line_number}:
```python
{line_content}
```

Variable state at this step:
```json
{locals_json}
```

Explain why line {line_number} is executing now."""


# ── Cache Key ─────────────────────────────────────────────────────

def make_cache_key(code: str, line_number: int, line_content: str, locals_dict: dict) -> str:
    """
    Content-addressable cache key for explanations.
    Two identical (code, line_number, line_content, locals) requests return the same explanation.
    """
    locals_hash = hashlib.sha256(
        json.dumps(locals_dict, sort_keys=True).encode()
    ).hexdigest()[:16]
    payload = json.dumps({
        "code": code[:200],        # First 200 chars of code
        "ln": line_number,
        "lc": line_content[:50],   # First 50 chars of line
        "lv": locals_hash,          # Variable-state fingerprint
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── LLM Router ────────────────────────────────────────────────────

class LLMRouter:
    """
    Routes explanation requests to the best available LLM provider.
    Tries providers in order until one succeeds.
    """
    
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self._http.aclose()
    
    async def stream_explain(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        ollama_endpoint: str | None = None,
        github_models_pat: str | None = None,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
        """
        Stream explanation tokens from the best available provider.
        
        Yields: (token: str, provider: LLMProvider)
        When done: yields ("__done__", provider)
        On error: yields (error_message, provider=LLMProvider.GITHUB_MODELS)
        """
        # 1. Check cache first
        cache_key = make_cache_key(code, line_number, line_content, locals_dict)
        cached_text = await self._get_cached(cache_key)
        if cached_text:
            logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
            # Stream cached text word-by-word for consistent streaming behavior
            for word in cached_text.split():
                yield word + " ", LLMProvider.OLLAMA_CLOUD
            yield "__done__", LLMProvider.OLLAMA_CLOUD
            return
        
        # 2. Build messages (system = fixed instructions, user = runtime context)
        user_message = USER_PROMPT_TEMPLATE.format(
            code=code[:2000],  # Truncate very long code to avoid token waste
            line_number=line_number,
            line_content=line_content,
            locals_json=json.dumps(locals_dict, indent=2),
        )
        
        # 3. Try providers in order
        providers_to_try = []
        
        # 1. Ollama Cloud (primary — free, no setup)
        if settings.ollama_cloud_url:
            providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url, cache_key))
        
        # 2. GitHub Models (fallback — requires PAT)
        pat = github_models_pat or settings.github_models_pat
        if pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))
        
        errors = []
        full_text: list[str] = []
        final_provider = LLMProvider.GITHUB_MODELS
        
        for provider, _endpoint, _cache_key in providers_to_try:
            try:
                if provider == LLMProvider.GITHUB_MODELS:
                    async for token in self._stream_github_models(SYSTEM_PROMPT, user_message, cache_key, github_models_pat):
                        full_text.append(token)
                        yield token, provider
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(SYSTEM_PROMPT, user_message, cache_key, ollama_endpoint):
                        full_text.append(token)
                        yield token, provider
                
                # Provider succeeded — record which one
                final_provider = provider
                yield "__done__", provider
                
                # Write successful explanation to cache for future requests
                if full_text:
                    combined = "".join(full_text)
                    await self._store_cached(
                        cache_key=cache_key,
                        text=combined,
                        provider_used=final_provider.value,
                        model_name=(
                            settings.github_models_model
                            if final_provider == LLMProvider.GITHUB_MODELS
                            else (settings.ollama_model or "llama3.2")
                        ),
                        line_number=line_number,
                    )
                return
                
            except Exception as e:
                logger.error(
                    "llm_provider_failed",
                    extra={"provider": provider.value, "error": str(e), "error_type": type(e).__name__},
                )
                errors.append(f"{provider.value}: {e}")
                continue
        
        # All providers failed - yield a helpful message
        error_msg = (
            "⚠️ No AI provider is available. "
            "Please set OLLAMA_CLOUD_URL or GITHUB_MODELS_PAT in your .env file.\n\n"
            f"Errors encountered: {'; '.join(errors[:2])}"
        )
        for word in error_msg.split():
            yield word + " ", LLMProvider.OLLAMA_CLOUD
        yield "__done__", LLMProvider.OLLAMA_CLOUD
    
    async def _stream_github_models(self, system_msg: str, user_msg: str, cache_key: str, github_models_pat: str | None = None) -> AsyncGenerator[str, None]:
        """Stream from GitHub Models API using true server-sent events.

        Uses stream=True so tokens appear as the model generates them,
        instead of waiting for the full response before yielding anything.

        The GitHub Models API is OpenAI-compatible. With stream=True it returns
        newline-delimited JSON chunks in the format:
            data: {"choices":[{"delta":{"content":"Hello"}}]}
            data: [DONE]
        """
        model = settings.github_models_model or "openai/gpt-4o-mini"
        url = "https://models.github.ai/inference/chat/completions"
        pat = github_models_pat or settings.github_models_pat

        headers = {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        }

        # Use stream=True so httpx does not buffer the full response body.
        # We stream line-by-line using aiter_lines().
        async with self._http.stream(
            "POST",
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "stream": True,
            },
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                # Read the full error body before raising (only on error, safe to buffer)
                error_body = await response.aread()
                logger.error(
                    f"GitHub API error: {response.status_code} - {error_body[:200]}"
                )
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            async for line in response.aiter_lines():
                # SSE lines are prefixed with "data: "
                if not line.startswith("data: "):
                    continue

                payload = line[len("data: "):]

                # The stream ends with "data: [DONE]"
                if payload.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(payload)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    # Malformed chunk — skip silently
                    continue
    
    async def _stream_ollama_cloud(
        self,
        system_msg: str,
        user_msg: str,
        cache_key: str,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream from Ollama Cloud API (https://ollama.com/api/chat).
        Primary provider — free, no setup required.
        Uses user-provided ollama_endpoint if available, otherwise falls back to settings.
        """
        base_endpoint = ollama_endpoint or settings.ollama_cloud_url
        if "localhost" in base_endpoint or "127.0.0.1" in base_endpoint:
            base_endpoint = base_endpoint.rstrip("/")
            if base_endpoint.endswith("/api"):
                url = f"{base_endpoint}/chat"
            else:
                url = f"{base_endpoint}/api/chat"
        else:
            url = f"{base_endpoint}/chat"
        headers = {"Content-Type": "application/json"}
        
        body = {
            "model": settings.ollama_model or "llama3.2",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "stream": True,
        }
        
        response = await self._http.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            logger.error(f"Ollama Cloud error: {response.status_code}")
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    # Stream word by word
                    for word in content.split():
                        yield word + " "
            except json.JSONDecodeError:
                continue

    async def grade_explanation(
        self,
        code: str,
        steps_json: str,
        user_answer: str,
        github_models_pat: str | None = None,
    ) -> dict[str, Any]:
        """
        Grade the student's answer comparing it to the code and execution trace.
        Returns a dict containing 'score', 'rating_suggestion', and 'feedback'.
        """
        system_grader_prompt = """You are an AI code tutor grading a student's explanation of a Python code execution trace.

You will be given:
1. The source code being analyzed.
2. The sequence of execution steps (variable states and lines executed).
3. The student's written explanation of how this code executes.

Your job:
1. Evaluate how accurately the student understands the execution flow, the variable state changes, and any conditional branch choices.
2. Assign an integer score from 0 to 100 representing their accuracy.
3. Suggest a review rating:
   - "again" (score < 60): fundamental misunderstandings or blank/incorrect answer.
   - "hard" (score 60-79): got the basic idea but missed important details, variable updates, or branch reasons.
   - "good" (score 80-94): correct explanation with minor details omitted.
   - "easy" (score 95-100): perfect explanation of the logic.
4. Provide a friendly, constructive 2-3 sentence feedback explaining what they got right and what (if anything) they missed. Do not repeat the prompt or include markdown other than plain text.

Your response must be a valid JSON object in this exact format:
{
  "score": 85,
  "rating_suggestion": "good",
  "feedback": "Your explanation accurately captures how the variables update in the loop. You correctly noted that the loop terminates after 8 iterations, though you didn't explicitly mention the final return value."
}"""

        user_content = f"""Code:
```python
{code}
```

Trace Steps:
```json
{steps_json}
```

Student Answer:
{user_answer}"""

        # Choose provider based on config
        pat = github_models_pat or settings.github_models_pat
        if pat:
            # Use GitHub Models (OpenAI-compatible)
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models grade response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models grade request failed: {e}")

        # Fallback to Ollama Cloud or general default JSON response
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama grade response: {e}")
            except Exception as e:
                logger.error(f"Ollama grade request failed: {e}")

        # Safe fallback
        return {
            "score": 75,
            "rating_suggestion": "good",
            "feedback": "Grading failed due to an LLM communication issue, but keep up the effort!",
        }

    async def diagnose_misconception(
        self,
        code: str,
        checkpoint_type: str,
        variable_name: str | None,
        correct_value: str,
        user_prediction: str,
        lineno: int,
        github_models_pat: str | None = None,
    ) -> dict[str, Any]:
        """
        Diagnose a student's misconception by comparing their wrong prediction
        with the correct interpreter state.
        Returns a dict containing 'tag' and 'explanation'.
        """
        system_prompt = """You are an AI code tutor analyzing a student's mistake during a code tracing exercise.

You will be given:
1. The Python code being executed.
2. The checkpoint type (e.g. branch_prediction, variable_prediction, exception_prediction).
3. The specific variable name (if applicable).
4. The correct value (interpreter's Ground Truth).
5. The student's incorrect predicted value (their Mental Model).
6. The line number of the executing code.

Your job:
1. Perform a misconception differential analysis. Compare the Ground Truth against the student's prediction. Determine the precise logic misconception that led to this wrong guess.
2. Formulate a short explanation (exactly 2-3 sentences) directly addressing the student. Explain WHY their guess is incorrect by pointing to the exact variables and control flow in the code. Do not apologize or use generic greetings.
3. Categorize the misconception into one of these strict tags:
   - "off_by_one" (for index, loop bounds, range errors)
   - "unexecuted_iteration" (student thought a loop ran when it didn't, or vice-versa)
   - "none_dereference" (student assumed a None variable had attributes or contents)
   - "state_mutation_confusion" (student didn't realize a variable mutated or thought it mutated incorrectly)
   - "conditional_evaluation_error" (student evaluated a branch condition incorrectly)
   - "type_confusion" (mistaking division types, list vs string operations, etc.)
   - "general_logic_error" (fallback if none of the above fit)

Your response must be a valid JSON object in this exact format:
{
  "tag": "state_mutation_confusion",
  "explanation": "You predicted that 'x' would remain 5. However, line 4 mutates 'x' by adding 10 to it on this loop iteration, making it 15."
}"""

        user_content = f"""Code:
```python
{code}
```

Line Number: {lineno}
Checkpoint Type: {checkpoint_type}
Variable: {variable_name or 'N/A'}
Interpreter Correct Value: {correct_value}
Student Incorrect Prediction: {user_prediction}"""

        # Choose provider based on config
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models diagnosis response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models diagnosis request failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama diagnosis response: {e}")
            except Exception as e:
                logger.error(f"Ollama diagnosis request failed: {e}")

        # Safe fallback
        return {
            "tag": "general_logic_error",
            "explanation": "Your prediction was different from the interpreter state. Trace the logic line-by-line to see where the values diverged.",
        }

    # ── Cache Layer ───────────────────────────────────────────────
    
    async def _get_cached(self, cache_key: str) -> Optional[str]:
        """Fetch cached explanation from Supabase."""
        if not settings.supabase_url or not settings.supabase_service_key:
            return None
        
        try:
            resp = await self._http.post(
                f"{settings.supabase_url}/rest/v1/rpc/get_explanation",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                },
                json={"p_cache_key": cache_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data[0].get("explanation_text")
        except Exception as e:
            logger.warning("cache_fetch_failed", extra={"error": str(e)})
        
        return None
    
    async def _store_cached(
        self,
        cache_key: str,
        text: str,
        provider_used: str,
        model_name: str,
        trace_id: str | None = None,
        line_number: int | None = None,
    ) -> None:
        """Store explanation in Supabase cache."""
        if not settings.supabase_url or not settings.supabase_service_key:
            return
        
        try:
            resp = await self._http.post(
                f"{settings.supabase_url}/rest/v1/explanations",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json={
                    "cache_key": cache_key,
                    "explanation_text": text,
                    "model_used": provider_used,
                    "model_name": model_name,
                    "cached": True,
                    "trace_id": trace_id,
                    "line_number": line_number,
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "cache_store_failed",
                    extra={"error": f"status={resp.status_code}, body={resp.text[:200]}"}
                )
        except Exception as e:
            logger.warning("cache_store_failed", extra={"error": str(e)})

    async def generate_code_repair_challenge(
        self,
        original_code: str,
        misconception_tag: str,
        github_models_pat: str | None = None,
    ) -> str:
        """
        Generate a dynamic programming challenge targeting a specific misconception
        inspired by the student's original trace code.
        """
        system_prompt = """You are an AI code tutor generating a custom practice challenge for a student.
The student recently struggled with a misconception of type: '{tag}' while tracing the provided code.

Your job:
1. Synthesize a brand new, short (5-10 lines), complete Python function.
2. Inject a logical bug into this new function that directly matches the misconception tag '{tag}' (e.g. an off-by-one index error, mutable default argument issue, none check bypass, etc.).
3. Add a concise prompt comment at the top explaining what the function is supposed to do, and instructing the student to spot the bug and write the corrected code.
4. Keep the output extremely clean, returning ONLY the python code with the prompt comment. Do not wrap in markdown or explain the answer.

Example Output format:
# TUTOR CHALLENGE: The function below is supposed to find the first even number in a list.
# Spot the bug (unexecuted iteration error) and write the corrected code.
def first_even(nums):
    for n in nums:
        if n % 2 == 0:
            return n
    return -1
"""

        user_content = f"Original Trace Code:\n```python\n{original_code}\n```\n\nMisconception Tag: {misconception_tag}"

        # Choose provider
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt.format(tag=misconception_tag)},
                            {"role": "user", "content": user_content},
                        ],
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"GitHub Models generate challenge failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_prompt.format(tag=misconception_tag)},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    return resp.json()["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Ollama generate challenge failed: {e}")

        # Default fallback code snippet
        return f"""# TUTOR CHALLENGE: Spot and fix the {misconception_tag.replace('_', ' ')} error below.
# Write the corrected code.
def fix_me(items):
    # Bug related to {misconception_tag} is present here
    return items
"""

    async def grade_code_repair(
        self,
        original_code: str,
        misconception_tag: str,
        user_fix: str,
        github_models_pat: str | None = None,
    ) -> dict[str, Any]:
        """
        Grade the student's code repair attempt targeting a specific misconception.
        """
        system_grader_prompt = f"""You are an AI code tutor grading a student's submission for a "Code Repair Challenge".
The student recently struggled with a misconception of type: '{misconception_tag}'.
They were given a practice code snippet containing a bug matching that misconception, and they have submitted their corrected code version.

Your job:
1. Determine if the student's corrected code successfully resolves the logical bug related to '{misconception_tag}'.
2. Assign an integer score from 0 to 100 representing the accuracy of their fix.
3. Suggest a review rating:
   - "again" (score < 60): failed to fix the bug, wrote invalid code, or left it blank.
   - "hard" (score 60-79): partially fixed the bug but introduced another issue or missed corner cases.
   - "good" (score 80-94): correct fix with slight inefficiencies.
   - "easy" (score 95-100): perfect, clean correction of the bug.
4. Provide a friendly, constructive 2-3 sentence feedback explaining what they got right and what (if anything) they missed. Do not repeat the prompt.

Your response must be a valid JSON object in this exact format:
{{
  "score": 90,
  "rating_suggestion": "good",
  "feedback": "Your correction successfully addresses the loop boundary check and avoids the off-by-one error by using range(len(lst)). Excellent fix!"
}}"""

        user_content = f"""Original Trace Code Reference:
{original_code}

Misconception tag: {misconception_tag}

Student Corrected Code submission:
{user_fix}"""

        # Choose provider
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models grade repair response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models grade repair request failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama grade repair response: {e}")
            except Exception as e:
                logger.error(f"Ollama grade repair request failed: {e}")

        # Safe fallback
        return {
            "score": 75,
            "rating_suggestion": "good",
            "feedback": "Grading failed due to an LLM communication issue, but keep up the effort!",
        }



# Global singleton
llm_router = LLMRouter()
