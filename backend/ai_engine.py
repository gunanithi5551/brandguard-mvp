"""
BrandGuard AI — Multi-Agent & Multimodal Compliance Engine

- Text Audit: CrewAI Compliance Agent powered by Gemini (gemini-3.5-flash-lite)
  against active ChromaDB guidelines, with robust JSON extraction and automatic
  fallback to direct google-genai structured JSON output so the API never throws
  an unhandled 500 on formatting quirks.
- Visual Audit: Direct Google Gemini Vision (gemini-3.5-flash-lite via google-genai)
  with a strict 25-second timeout and structured JSON schema output.
- Security: Reads GEMINI_API_KEY exclusively from environment variables (.env).
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("brandguard.ai_engine")

import random
import time

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]

VISION_TIMEOUT_SECONDS = 60
_EXHAUSTED_MODELS_UNTIL: Dict[str, float] = {}


def _get_api_key_pool(primary_key: str) -> List[str]:
    """Collect unique API keys from GEMINI_API_KEYS, GEMINI_API_KEY, and GEMINI_API_KEY_BACKUP."""
    raw_list = [primary_key]
    multi = os.getenv("GEMINI_API_KEYS") or ""
    raw_list.extend(k.strip() for k in multi.split(",") if k.strip())
    backup = (os.getenv("GEMINI_API_KEY_BACKUP") or "").strip()
    if backup:
        raw_list.append(backup)

    seen = set()
    pool = []
    for k in raw_list:
        if k and not k.lower().startswith("your_") and k not in seen:
            seen.add(k)
            pool.append(k)
    return pool


def _make_genai_client(api_key: str):
    """Allow 25s for multimodal vision while keeping attempts=1 so fallback rotates fast."""
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=25_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def _generate_with_fallback(client, *, model: str, api_key: str = "", **kwargs):
    candidates = [model] + [m for m in FALLBACK_MODELS if m != model]
    key_pool = _get_api_key_pool(api_key or get_gemini_api_key())
    last_err = None

    for round_idx in range(2):
        for key_idx, active_key in enumerate(key_pool):
            active_client = client if (round_idx == 0 and key_idx == 0) else _make_genai_client(active_key)
            for candidate in candidates:
                cache_key = f"{active_key[:10]}:{candidate}"
                if time.time() < _EXHAUSTED_MODELS_UNTIL.get(cache_key, 0):
                    continue
                try:
                    return active_client.models.generate_content(model=candidate, **kwargs)
                except Exception as exc:
                    last_err = exc
                    msg = str(exc).lower()
                    if "429" in msg or "resource_exhausted" in msg or "perday" in msg:
                        _EXHAUSTED_MODELS_UNTIL[cache_key] = time.time() + 3600
                        logger.warning("Quota exhausted for %s on key #%d; skipping.", candidate, key_idx + 1)
                        continue
                    if any(
                        token in msg
                        for token in (
                            "503",
                            "unavailable",
                            "504",
                            "404",
                            "not found",
                            "timeout",
                            "timed out",
                            "deadline",
                        )
                    ):
                        logger.warning(
                            "Round %d (key #%d): %s unavailable (%s); rotating.",
                            round_idx + 1,
                            key_idx + 1,
                            candidate,
                            type(exc).__name__,
                        )
                        time.sleep(0.3 + random.uniform(0.05, 0.2))
                        continue
                    raise

    raise last_err or RuntimeError("All Gemini models and API keys are temporarily unavailable.")


class AIConfigurationError(RuntimeError):
    """Raised when GEMINI_API_KEY is missing or invalid."""


class AITimeoutError(TimeoutError):
    """Raised when an AI compliance audit exceeds its time budget."""


def get_gemini_api_key() -> str:
    """Return GEMINI_API_KEY from environment without ever hardcoding a secret."""
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key or key.lower().startswith("your_") or key == "replace_me":
        return ""
    return key


def is_ai_configured() -> bool:
    return bool(get_gemini_api_key())


def _require_api_key() -> str:
    key = get_gemini_api_key()
    if not key:
        raise AIConfigurationError(
            "GEMINI_API_KEY is not configured. Please add a valid GEMINI_API_KEY "
            "to your .env file or Render environment variables."
        )
    return key


def _format_guidelines_block(guidelines: List[Dict[str, Any]]) -> str:
    if not guidelines:
        return "No active brand guidelines are currently loaded."
    lines = []
    for idx, rule in enumerate(guidelines, start=1):
        title = rule.get("title", f"Rule {idx}")
        content = rule.get("content", "")
        lines.append(f"{idx}. [{title}] {content}")
    return "\n".join(lines)


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """Robustly extract a JSON object from LLM text, including markdown fences."""
    if not raw_text or not isinstance(raw_text, str):
        raise ValueError("Empty AI response")

    text = raw_text.strip()
    # Strip markdown ```json ... ``` fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: locate outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Could not parse a valid JSON object from AI output.")


def _normalize_status(raw_status: Any, score: int, broken_rules: List[str]) -> str:
    val = str(raw_status or "").strip().lower()
    if val in {"approved", "flagged", "violation"}:
        return val
    if val in {"pass", "passed", "compliant"}:
        return "approved"
    if val in {"warn", "warning", "needs_review", "review"}:
        return "flagged"
    if val in {"fail", "failed", "rejected", "non-compliant", "non_compliant"}:
        return "violation"
    if score >= 85 and not broken_rules:
        return "approved"
    if score >= 60:
        return "flagged"
    return "violation"


def _normalize_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        num = default
    return max(0, min(100, num))


def _normalize_text_audit(
    payload: Dict[str, Any],
    original_text: str,
    guidelines_checked: int,
) -> Dict[str, Any]:
    broken_rules = _normalize_str_list(payload.get("broken_rules"))
    score = _clamp_score(payload.get("score"), default=100 if not broken_rules else 40)
    status = _normalize_status(payload.get("status"), score, broken_rules)
    explanation = str(
        payload.get("explanation")
        or (
            "The copy aligns with all active brand guidelines."
            if status == "approved"
            else "The copy violates one or more active brand guidelines."
        )
    ).strip()
    suggestion = str(payload.get("suggestion") or original_text).strip()

    return {
        "status": status,
        "score": score,
        "broken_rules": broken_rules,
        "explanation": explanation,
        "suggestion": suggestion,
        "guidelines_checked": int(guidelines_checked),
    }


def _normalize_visual_audit(
    payload: Dict[str, Any],
    guidelines_checked: int,
) -> Dict[str, Any]:
    broken_rules = _normalize_str_list(payload.get("broken_rules"))
    visual_findings = _normalize_str_list(payload.get("visual_findings"))
    text_findings = _normalize_str_list(payload.get("text_in_image_findings"))
    actionable_fixes = _normalize_str_list(payload.get("actionable_fixes"))
    score = _clamp_score(payload.get("score"), default=100 if not broken_rules else 35)
    status = _normalize_status(payload.get("status"), score, broken_rules)
    explanation = str(
        payload.get("explanation")
        or (
            "The visual asset complies with active brand guidelines."
            if status == "approved"
            else "The visual asset contains brand compliance issues that require revision."
        )
    ).strip()

    return {
        "status": status,
        "score": score,
        "broken_rules": broken_rules,
        "visual_findings": visual_findings,
        "text_in_image_findings": text_findings,
        "explanation": explanation,
        "actionable_fixes": actionable_fixes,
        "guidelines_checked": int(guidelines_checked),
    }


def _build_text_prompt(copy_text: str, guidelines_block: str) -> str:
    return f"""You are BrandGuard AI, a strict enterprise brand-governance compliance auditor.

Evaluate the marketing copy below ONLY against the Active Brand Guidelines provided.

ACTIVE BRAND GUIDELINES:
{guidelines_block}

MARKETING COPY TO AUDIT:
\"\"\"{copy_text}\"\"\"

Return ONLY a valid JSON object (no markdown, no extra prose) with this exact schema:
{{
  "status": "approved" | "flagged" | "violation",
  "score": <integer 0 to 100>,
  "broken_rules": [<list of concise strings quoting/naming each violated rule; empty list if approved>],
  "explanation": "<clear plain-English explanation of the compliance findings>",
  "suggestion": "<fully compliant, polished enterprise rewrite of the copy>"
}}

Scoring rules:
- 85-100 and empty broken_rules -> "approved"
- 55-84 or minor tone/clarity concerns -> "flagged"
- 0-54 or any direct policy violation -> "violation"
"""


def _build_vision_prompt(guidelines_block: str, caption: Optional[str]) -> str:
    caption_section = (
        f'OPTIONAL AD CAPTION:\n"""{caption.strip()}"""'
        if caption and caption.strip()
        else "OPTIONAL AD CAPTION: (none provided)"
    )
    return f"""You are BrandGuard AI, a strict multimodal brand-governance auditor.

Inspect the attached advertisement/creative image (including all visible typography, colors, contrast, layout, and claims) and the optional caption against the Active Brand Guidelines.

ACTIVE BRAND GUIDELINES:
{guidelines_block}

{caption_section}

Return ONLY a valid JSON object (no markdown, no extra prose) with this exact schema:
{{
  "status": "approved" | "flagged" | "violation",
  "score": <integer 0 to 100>,
  "broken_rules": [<list of violated rules; empty list if approved>],
  "visual_findings": [<observations about layout, colors, contrast, typography, visual hierarchy>],
  "text_in_image_findings": [<exact text detected in the image and compliance assessment of that text>],
  "explanation": "<clear plain-English summary of visual & textual compliance>",
  "actionable_fixes": [<concrete, specific edits to make the creative 100% compliant; empty if approved>]
}}

Scoring rules:
- 85-100 and empty broken_rules -> "approved"
- 55-84 or minor visual/copy improvements needed -> "flagged"
- 0-54 or any direct policy violation -> "violation"
"""


def _run_crewai_text_audit(prompt: str, api_key: str) -> str:
    """Run CrewAI single-agent compliance review using Gemini 2.5 Flash."""
    from crewai import Agent, Crew, LLM, Process, Task

    llm = LLM(
        model=f"gemini/{MODEL_NAME}",
        api_key=api_key,
        temperature=0.1,
    )
    auditor = Agent(
        role="Enterprise Brand Compliance Auditor",
        goal="Audit marketing copy strictly against active brand guidelines and output valid JSON.",
        backstory=(
            "You are a senior corporate brand governance specialist who enforces "
            "tone, terminology, regulatory claims, and style rules with zero ambiguity."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    audit_task = Task(
        description=prompt,
        expected_output=(
            "A single raw JSON object with keys: status, score, broken_rules, "
            "explanation, suggestion."
        ),
        agent=auditor,
    )
    crew = Crew(
        agents=[auditor],
        tasks=[audit_task],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    return str(result)


def _call_gemini_text_json(prompt: str, api_key: str) -> str:
    """Direct Google GenAI structured JSON call (used as reliable fallback)."""
    from google.genai import types

    client = _make_genai_client(api_key)
    response = _generate_with_fallback(
        client,
        model=MODEL_NAME,
        api_key=api_key,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return response.text or ""


def _call_gemini_vision_json(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    api_key: str,
) -> str:
    """Direct Google GenAI multimodal Vision call with structured JSON output."""
    from google.genai import types

    client = _make_genai_client(api_key)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = _generate_with_fallback(
        client,
        model=MODEL_NAME,
        api_key=api_key,
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return response.text or ""


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "api_key_invalid",
            "api key not valid",
            "invalid api key",
            "permission denied",
            "unauthenticated",
            "401",
            "403",
        )
    )


def review_text_compliance(
    text: str,
    guidelines: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Audit marketing copy using CrewAI + Gemini (gemini-3.5-flash-lite), automatically
    falling back to direct Gemini structured JSON output if CrewAI formatting or
    execution fails.
    """
    api_key = _require_api_key()
    guidelines_block = _format_guidelines_block(guidelines)
    prompt = _build_text_prompt(text, guidelines_block)
    guidelines_count = len(guidelines)

    # 1. Primary path: CrewAI + Gemini
    try:
        crew_output = _run_crewai_text_audit(prompt, api_key)
        parsed = _extract_json_object(crew_output)
        return _normalize_text_audit(parsed, text, guidelines_count)
    except Exception as crew_exc:
        if _is_auth_error(crew_exc):
            raise AIConfigurationError(
                "Your GEMINI_API_KEY was rejected by Google AI. Please verify the key."
            ) from crew_exc
        logger.warning(
            "CrewAI audit fallback triggered (%s: %s). Falling back to direct Gemini JSON.",
            type(crew_exc).__name__,
            crew_exc,
        )

    # 2. Safe fallback path: direct Gemini structured JSON output
    try:
        direct_output = _call_gemini_text_json(prompt, api_key)
        parsed = _extract_json_object(direct_output)
        return _normalize_text_audit(parsed, text, guidelines_count)
    except Exception as exc:
        if _is_auth_error(exc):
            raise AIConfigurationError(
                "Your GEMINI_API_KEY was rejected by Google AI. Please verify the key."
            ) from exc
        raise RuntimeError(f"AI text compliance audit failed: {exc}") from exc


def review_image_compliance(
    image_bytes: bytes,
    mime_type: str,
    guidelines: List[Dict[str, Any]],
    caption: Optional[str] = None,
    timeout_seconds: int = VISION_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Audit an advertisement image + optional caption via Google Gemini Vision
    (gemini-3.5-flash-lite) with a strict 25-second timeout and structured JSON output.
    """
    api_key = _require_api_key()
    guidelines_block = _format_guidelines_block(guidelines)
    prompt = _build_vision_prompt(guidelines_block, caption)
    guidelines_count = len(guidelines)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _call_gemini_vision_json,
            image_bytes,
            mime_type,
            prompt,
            api_key,
        )
        try:
            raw_output = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise AITimeoutError(
                f"Visual compliance audit timed out after {timeout_seconds} seconds. "
                "Please try again with a smaller image."
            ) from exc
        except Exception as exc:
            if _is_auth_error(exc):
                raise AIConfigurationError(
                    "Your GEMINI_API_KEY was rejected by Google AI. Please verify the key."
                ) from exc
            raise RuntimeError(f"AI visual compliance audit failed: {exc}") from exc

    parsed = _extract_json_object(raw_output)
    return _normalize_visual_audit(parsed, guidelines_count)
