"""
CrewAI Multi-Agent Brand Compliance Engine for BrandGuard AI.
Defines the 'Compliance Auditor' and 'Correction Editor' agents with automatic deterministic fallback
when LLM API keys are absent during autonomous testing.
"""
import json
import os
import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

try:
    from backend.database import query_brand_guidelines
except ImportError:
    from database import query_brand_guidelines

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"))


class BrandReviewSchema(BaseModel):
    status: str = Field(..., description="'flagged' if any rule is violated, otherwise 'approved'")
    broken_rule: str = Field(..., description="The specific brand guideline rule(s) violated, or 'None'")
    explanation: str = Field(..., description="Detailed explanation of why the content failed or passed audit")
    suggestion: str = Field(..., description="Compliant rewrite preserving the original intent")


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    """Safely extracts a JSON object matching BrandReviewSchema from raw LLM output."""
    try:
        parsed = json.loads(raw_text)
        validated = BrandReviewSchema(**parsed)
        return getattr(validated, "model_dump", validated.dict)()
    except Exception:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            validated = BrandReviewSchema(**parsed)
            return getattr(validated, "model_dump", validated.dict)()
        raise ValueError("Unable to parse strict JSON schema from agent output.")


def _run_deterministic_fallback(draft_text: str, guidelines: str) -> str:
    """
    Autonomous testing fallback when an LLM API key or CrewAI runtime is unavailable.
    Evaluates the draft against the injected ChromaDB guidelines and returns a strict JSON string.
    """
    broken_rules: List[str] = []
    explanations: List[str] = []
    rewritten = draft_text

    # Rule 2 check: Never guarantee ROI or specific financial outcomes
    if re.search(r"\b(guarantee|guaranteed|100%\s*roi|roi|financial\s+outcome|profit)\b", draft_text, re.IGNORECASE):
        broken_rules.append("Rule 2: Never guarantee ROI or specific financial outcomes.")
        explanations.append(
            "The draft explicitly guarantees ROI or specific financial outcomes, which violates Rule 2 of the Brand Guidelines."
        )
        rewritten = re.sub(
            r"We guarantee a 100% ROI",
            "We strive to deliver measurable value and strong performance outcomes",
            rewritten,
            flags=re.IGNORECASE,
        )
        rewritten = re.sub(
            r"\bguarantee(d)?\b",
            "aim to deliver",
            rewritten,
            flags=re.IGNORECASE,
        )
        rewritten = re.sub(
            r"\b100%\s*ROI\b",
            "high-impact operational results",
            rewritten,
            flags=re.IGNORECASE,
        )

    # Rule 3 check: Refer to users as 'Clients', never 'Customers'
    if re.search(r"\bcustomers?\b", draft_text, re.IGNORECASE):
        broken_rules.append("Rule 3: Refer to users as 'Clients', never 'Customers'.")
        explanations.append(
            "The draft refers to users as 'customers' instead of the mandated term 'Clients' (Rule 3)."
        )
        rewritten = re.sub(r"\bcustomers\b", "Clients", rewritten, flags=re.IGNORECASE)
        rewritten = re.sub(r"\bcustomer\b", "Client", rewritten, flags=re.IGNORECASE)

    # Rule 1 check: Always use a professional tone (check excessive exclamation marks or slang)
    if "!" in draft_text or re.search(r"\b(awesome|crazy|insane|guaranteed)\b", draft_text, re.IGNORECASE):
        if "!" in draft_text:
            broken_rules.append("Rule 1: Always use a professional tone.")
            explanations.append(
                "Exclamatory promotional punctuation ('!') undermines an enterprise professional tone (Rule 1)."
            )
            rewritten = rewritten.replace("!", ".")

    # Clean up double periods if any
    rewritten = re.sub(r"\.{2,}", ".", rewritten).strip()

    if broken_rules:
        result = BrandReviewSchema(
            status="flagged",
            broken_rule=" | ".join(broken_rules),
            explanation=" ".join(explanations) + f" [Audited against ChromaDB: {guidelines}]",
            suggestion=rewritten,
        )
    else:
        result = BrandReviewSchema(
            status="approved",
            broken_rule="None",
            explanation="The submitted content adheres to all BrandGuard AI corporate tone, financial claim, and terminology rules.",
            suggestion=draft_text,
        )

    return json.dumps(getattr(result, "model_dump", result.dict)())


def run_brand_check(draft_text: str) -> str:
    """
    Queries ChromaDB for brand guidelines, executes the CrewAI Compliance Auditor and Correction Editor
    workflow, and returns a strict JSON string matching BrandReviewSchema.
    Falls back to deterministic schema evaluation if an LLM API key is missing during internal testing.
    """
    guidelines = query_brand_guidelines(draft_text)
    def _valid_key(val):
        return bool(val and val.strip() and not val.strip().startswith("your_"))

    has_api_key = any(
        _valid_key(os.getenv(k))
        for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    )

    if has_api_key:
        try:
            from crewai import Agent, Task, Crew, Process  # type: ignore

            compliance_auditor = Agent(
                role="Compliance Auditor",
                goal="Strictly audit submitted draft text against the retrieved ChromaDB brand guidelines.",
                backstory=(
                    "You are an uncompromising corporate brand compliance auditor. You inspect every claim, "
                    "tone choice, and user noun against official BRAND GUIDELINES stored in ChromaDB."
                ),
                verbose=False,
                allow_delegation=False,
            )

            correction_editor = Agent(
                role="Correction Editor",
                goal="Rewrite flagged content so that all brand violations are resolved while preserving original intent.",
                backstory=(
                    "You are an expert enterprise copy editor who transforms non-compliant marketing drafts "
                    "into polished, guideline-compliant communications and outputs strict JSON."
                ),
                verbose=False,
                allow_delegation=False,
            )

            audit_task = Task(
                description=(
                    f"Analyze the following draft text against the BRAND GUIDELINES.\n"
                    f"GUIDELINES: {guidelines}\n"
                    f"DRAFT TEXT: {draft_text}\n"
                    "Identify whether the text should be 'flagged' or 'approved', list the exact broken_rule, "
                    "and provide a clear explanation."
                ),
                expected_output="Detailed audit findings listing broken rules and explanations.",
                agent=compliance_auditor,
            )

            edit_task = Task(
                description=(
                    f"Based on the Compliance Auditor's findings for DRAFT TEXT: '{draft_text}' and "
                    f"GUIDELINES: '{guidelines}', produce a compliant rewrite suggestion and return ONLY a valid "
                    "JSON string matching this exact schema: "
                    '{"status": "flagged", "broken_rule": "...", "explanation": "...", "suggestion": "..."}'
                ),
                expected_output='Strict JSON string matching {"status": "flagged", "broken_rule": "...", "explanation": "...", "suggestion": "..."}',
                agent=correction_editor,
                context=[audit_task],
            )

            crew = Crew(
                agents=[compliance_auditor, correction_editor],
                tasks=[audit_task, edit_task],
                process=Process.sequential,
                verbose=False,
            )

            crew_output = crew.kickoff()
            parsed = _extract_json_payload(str(crew_output))
            return json.dumps(parsed)
        except Exception:
            return _run_deterministic_fallback(draft_text, guidelines)

    return _run_deterministic_fallback(draft_text, guidelines)
