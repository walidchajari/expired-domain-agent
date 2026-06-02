import json
import time
import logging
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)


def _create_client():
    provider = settings.ai_provider.lower()
    if provider == "gemini":
        from google import genai as gemini_client
        return gemini_client.Client(api_key=settings.gemini_api_key)
    else:
        from openai import OpenAI
        return OpenAI(api_key=settings.openai_api_key)

AI_PROMPT_TEMPLATE = """Act as a professional domain investor and startup branding expert.

Analyze this expired .com domain for resale value and startup branding potential:

Domain: {domain}
Length: {length} characters
Registered TLDs: {reg}
Backlinks: {bl}
Domain Authority (DP): {dp}
Wayback Age: {wby}

Rate the domain from 0 to 100 on these dimensions:

1. Brandability – Can this be a strong brand name? Is it catchy, distinctive?
2. Startup Potential – Would a startup use this name? Is it relevant to modern industries?
3. Pronounceability – Is it easy to say and spell over the phone?
4. Memorability – Will people remember it after hearing it once?
5. Resale Potential – What is its resale value on the aftermarket?

Respond ONLY with valid JSON in this exact format:
{{
  "brandability": <0-100>,
  "startup_potential": <0-100>,
  "pronounceability": <0-100>,
  "memorability": <0-100>,
  "resale_potential": <0-100>,
  "reasoning": "<one-sentence summary>"
}}
"""


class DomainAIScorer:
    def __init__(self):
        self.client = _create_client()
        self.provider = settings.ai_provider.lower()
        self.model_name = settings.gemini_model if self.provider == "gemini" else settings.openai_model
        self.timeout = settings.ai_scoring_timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
    )
    def score_domain(self, domain: str, length: int, reg: int, bl: str, dp: str, wby: str) -> Optional[dict]:
        prompt = AI_PROMPT_TEMPLATE.format(
            domain=domain,
            length=length,
            reg=reg,
            bl=bl,
            dp=dp,
            wby=wby,
        )
        try:
            if self.provider == "gemini":
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={"temperature": 0.3, "max_output_tokens": 2000},
                )
                content = response.text.strip()
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=self.timeout,
                )
                content = response.choices[0].message.content.strip()

            # Strip markdown fences if present
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(line for line in lines if not line.startswith("```"))
            data = json.loads(content)

            return {
                "brandability": self._clamp(data.get("brandability", 50)),
                "startup_potential": self._clamp(data.get("startup_potential", 50)),
                "pronounceability": self._clamp(data.get("pronounceability", 50)),
                "memorability": self._clamp(data.get("memorability", 50)),
                "resale_potential": self._clamp(data.get("resale_potential", 50)),
                "ai_raw_response": json.dumps(data),
                "reasoning": data.get("reasoning", ""),
            }
        except json.JSONDecodeError:
            logger.warning("AI response JSON parse failed for %s: %s", domain, content[:200])
            # Attempt to repair truncated JSON
            try:
                repaired = self._repair_json(content)
                if repaired:
                    logger.info("Repaired truncated JSON for %s", domain)
                    return repaired
            except Exception:
                pass
            return None
        except Exception:
            logger.exception("AI API error for %s (provider=%s)", domain, self.provider)
            return None

    @staticmethod
    def _repair_json(content: str) -> Optional[dict]:
        """Attempt to fix truncated JSON by adding missing closing brackets."""
        if not content:
            return None
        # Count opening and closing braces
        opens = content.count("{")
        closes = content.count("}")
        if opens == closes:
            return None  # JSON was complete, just malformed
        if opens > closes:
            # Add missing closing braces
            content += "}" * (opens - closes)
        try:
            data = json.loads(content)
            return {
                "brandability": DomainAIScorer._clamp(data.get("brandability", 50)),
                "startup_potential": DomainAIScorer._clamp(data.get("startup_potential", 50)),
                "pronounceability": DomainAIScorer._clamp(data.get("pronounceability", 50)),
                "memorability": DomainAIScorer._clamp(data.get("memorability", 50)),
                "resale_potential": DomainAIScorer._clamp(data.get("resale_potential", 50)),
                "ai_raw_response": json.dumps(data),
                "reasoning": data.get("reasoning", ""),
            }
        except (json.JSONDecodeError, Exception):
            return None

    @staticmethod
    def _clamp(v: float) -> int:
        return max(0, min(100, int(round(v))))


# ------------------------------------------------------------------
# Investor scoring formula
# ------------------------------------------------------------------
def compute_final_score(
    ai_scores: dict,
    length: int,
    reg: int,
) -> float:
    """
    Weighted scoring formula (prioritizing resale value over SEO):
    25% Brandability
    25% Resale Potential
    15% Startup Potential
    10% Pronounceability
    10% Memorability
    10% Length score
    5%  Registered TLD count
    """
    brand = ai_scores.get("brandability", 50)
    resale = ai_scores.get("resale_potential", 50)
    pronounce = ai_scores.get("pronounceability", 50)
    memo = ai_scores.get("memorability", 50)
    startup = ai_scores.get("startup_potential", 50)

    # Length score: ideal 5-7 chars, penalize longer/shorter
    if 5 <= length <= 7:
        length_score = 100
    elif length in (4, 8):
        length_score = 80
    elif length in (9, 10):
        length_score = 60
    else:
        length_score = 40

    # Reg score: more TLDs registered = more demand
    reg_score = min(100, reg * 10)

    final = (
        0.25 * brand
        + 0.25 * resale
        + 0.15 * startup
        + 0.10 * pronounce
        + 0.10 * memo
        + 0.10 * length_score
        + 0.05 * reg_score
    )
    return round(final, 2)


# ------------------------------------------------------------------
# Batch scoring
# ------------------------------------------------------------------
def score_domains(domains: list[dict], enabled: bool = True) -> list[dict]:
    if not enabled:
        logger.info("AI scoring disabled – using rule-based scores only")
        for d in domains:
            d.update({
                "brandability": 50,
                "startup_potential": 50,
                "pronounceability": 50,
                "memorability": 50,
                "resale_potential": 50,
                "ai_raw_response": "",
            })
            d["final_score"] = compute_final_score(d, d["length"], d["reg"])
        return domains

    scorer = DomainAIScorer()
    scored = []
    total = len(domains)

    for i, domain_data in enumerate(domains):
        logger.info("Scoring [%d/%d] %s", i + 1, total, domain_data["domain"])
        ai = scorer.score_domain(
            domain=domain_data["domain"],
            length=domain_data["length"],
            reg=domain_data["reg"],
            bl=domain_data.get("bl", ""),
            dp=domain_data.get("dp", ""),
            wby=domain_data.get("wby", ""),
        )

        if ai:
            domain_data.update(ai)
        else:
            # Fallback to average scores
            domain_data.update({
                "brandability": 50,
                "startup_potential": 50,
                "pronounceability": 50,
                "memorability": 50,
                "resale_potential": 50,
                "ai_raw_response": "",
            })

        domain_data["final_score"] = compute_final_score(
            domain_data, domain_data["length"], domain_data["reg"]
        )
        scored.append(domain_data)

        # Rate limit: small delay between calls
        time.sleep(0.5)

    return scored
