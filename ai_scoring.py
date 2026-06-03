import json
import time
import logging
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from english_filter import compute_english_score
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
# EXPIREDDOMAINS EXPERT MODE: metric parsers
# ------------------------------------------------------------------

def _parse_numeric(value: str) -> int:
    """Parse numeric strings like '1.2k', '500', '-' into int."""
    if not value or value in ("-", "N/A", ""):
        return 0
    value = value.strip().lower().replace(",", "").replace("\u00a0", "").replace("\xa0", "")
    import re
    match = re.match(r"([\d.]+)([kmb]?)", value)
    if not match:
        return 0
    num = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1_000_000
    elif suffix == "b":
        num *= 1_000_000_000
    return int(num)


# ------------------------------------------------------------------
# EXPIREDDOMAINS EXPERT MODE: scoring formula
# ------------------------------------------------------------------

EXPERT_WEIGHTS = {
    "brandability": 0.35,
    "commercial_intent": 0.20,
    "reg": 0.15,
    "pronounceability": 0.10,
    "dp": 0.10,
    "age": 0.05,
    "geo": 0.03,
    "backlinks": 0.02,
}


def compute_final_score(
    ai_scores: dict,
    domain_data: dict,
    english_scores: Optional[dict] = None,
    geo_score: int = 0,
    startup_score: int = 0,
    liquid_score: int = 0,
) -> float:
    """
    ADVANCED DOMAIN INVESTOR MODE scoring model:

    35%  Brandability Score      – AI-assessed brand strength
    20%  Commercial Intent       – industry keyword value
    15%  REG Score               – registered TLD count
    10%  Pronounceability        – ease of pronunciation & spelling
    10%  DP Score                – unique referring domains
    5%   Age Score               – first archive year (WBY)
    3%   Geo Score               – geographic keyword value
    2%   Backlink Quality Score  – backlink count quality
    """
    # 1. Brandability Score (35%) — from AI
    brand = ai_scores.get("brandability", 50)

    # 2. Commercial Intent (20%) — from english_filter
    commercial = (english_scores or {}).get("commercial_intent_score", 0)

    # 3. REG Score (15%) — more TLDs = stronger demand
    reg = domain_data.get("reg", 0)
    if reg >= 20:
        reg_score = 100
    elif reg >= 10:
        reg_score = 85
    elif reg >= 5:
        reg_score = 65
    elif reg >= 3:
        reg_score = 45
    elif reg >= 1:
        reg_score = 20
    else:
        reg_score = 0

    # 4. Pronounceability (10%) — from english_filter
    pronounce = (english_scores or {}).get("pronounceability_score", 50)

    # 5. DP Score (10%) — unique referring domains
    dp_val = _parse_numeric(domain_data.get("dp", "0"))
    if dp_val >= 1000:
        dp_score = 100
    elif dp_val >= 100:
        dp_score = 80
    elif dp_val >= 10:
        dp_score = 50
    elif dp_val > 0:
        dp_score = 25
    else:
        dp_score = 0

    # 6. Age Score (5%) — years since first archive (WBY)
    from datetime import datetime
    wby_val = _parse_numeric(domain_data.get("wby", "0"))
    current_year = datetime.now().year
    age = current_year - wby_val if wby_val > 1900 and wby_val <= current_year else 0
    if age >= 15:
        age_score = 100
    elif age >= 10:
        age_score = 80
    elif age >= 5:
        age_score = 60
    elif age >= 2:
        age_score = 30
    else:
        age_score = 0

    # 7. Geo Score (3%)
    geo_score = min(100, max(0, geo_score))

    # 8. Backlink Quality Score (2%)
    bl_val = _parse_numeric(domain_data.get("bl", "0"))
    if bl_val >= 1000:
        bl_score = 100
    elif bl_val >= 100:
        bl_score = 70
    elif bl_val >= 10:
        bl_score = 40
    elif bl_val > 0:
        bl_score = 15
    else:
        bl_score = 0

    final = (
        0.35 * brand
        + 0.20 * commercial
        + 0.15 * reg_score
        + 0.10 * pronounce
        + 0.10 * dp_score
        + 0.05 * age_score
        + 0.03 * geo_score
        + 0.02 * bl_score
    )
    return round(final, 2)


# ------------------------------------------------------------------
# Pre-filter for AI scoring
# ------------------------------------------------------------------
def _meets_ai_thresholds(domain_data: dict) -> bool:
    """Skip AI call for domains that don't meet minimum quality thresholds."""
    # REG >= 3: registered on 3+ TLDs
    if domain_data.get("reg", 0) < 3:
        return False
    # Length <= 12
    if domain_data.get("length", 99) > 12:
        return False
    # BL >= 1: at least 1 backlink
    bl_val = _parse_numeric(domain_data.get("bl", "0"))
    if bl_val < 1:
        return False
    return True


# ------------------------------------------------------------------
# Batch scoring
# ------------------------------------------------------------------
def score_domains(domains: list[dict], enabled: bool = True) -> list[dict]:
    # Deferred import to avoid circular dependency
    from domain_classifier import compute_geo_score, compute_startup_pattern_score, compute_liquid_score

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
            eng = compute_english_score(d["domain"])
            d["english_scores"] = eng
            geo = compute_geo_score(d["domain"])
            startup = compute_startup_pattern_score(d["domain"])
            liquid = compute_liquid_score(d["domain"])
            d["startup_pattern_score"] = startup
            d["liquid_score"] = liquid
            d["final_score"] = compute_final_score(d, d, eng, geo, startup, liquid)
        return domains

    scorer = DomainAIScorer()
    scored = []
    total = len(domains)

    for i, domain_data in enumerate(domains):
        # Pre-filter: only call AI for domains meeting minimum thresholds
        use_ai = _meets_ai_thresholds(domain_data)

        if not use_ai:
            logger.info("Skipping AI for %s (REG=%s DP=%s len=%s BL=%s)",
                        domain_data["domain"], domain_data.get("reg"),
                        domain_data.get("dp"), domain_data.get("length"),
                        domain_data.get("bl"))

        # Compute English word scores before AI call
        eng = compute_english_score(domain_data["domain"])
        domain_data["english_scores"] = eng

        if use_ai:
            logger.info("Scoring [%d/%d] %s", i + 1, total, domain_data["domain"])
            ai = scorer.score_domain(
                domain=domain_data["domain"],
                length=domain_data["length"],
                reg=domain_data["reg"],
                bl=domain_data.get("bl", ""),
                dp=domain_data.get("dp", ""),
                wby=domain_data.get("wby", ""),
            )
        else:
            ai = None

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

        geo = compute_geo_score(domain_data["domain"])
        startup = compute_startup_pattern_score(domain_data["domain"])
        liquid = compute_liquid_score(domain_data["domain"])
        domain_data["geo_score"] = geo
        domain_data["startup_pattern_score"] = startup
        domain_data["liquid_score"] = liquid
        domain_data["final_score"] = compute_final_score(
            domain_data, domain_data, eng, geo, startup, liquid
        )
        scored.append(domain_data)

        # Rate limit: small delay between calls
        time.sleep(0.5)

    return scored
