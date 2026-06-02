"""
Machine learning feedback system for personalized domain investing.

Learns user preferences from BUY/GOOD/BAD/SKIP ratings and adjusts
future scoring to prioritize domains matching the investor's style.
"""
import logging
import re
from collections import Counter, defaultdict
from typing import Optional

import numpy as np

from database import (
    get_feedback_history,
    upsert_investor_profile,
    get_investor_profile,
    domain_exists,
)

logger = logging.getLogger(__name__)

# Feature names used for the investor profile
FEATURES = [
    "length",
    "reg",
    "brandability",
    "resale_potential",
    "pronounceability",
    "memorability",
    "startup_potential",
]

RATING_WEIGHTS = {
    "BUY": 2.0,
    "GOOD": 1.0,
    "BAD": -0.5,
    "SKIP": -1.0,
}


def _domain_features(domain: str) -> dict:
    """Extract linguistic features from a domain name (without TLD)."""
    name = domain.replace(".com", "").lower()
    features = {
        "length": len(name),
        "vowel_ratio": sum(1 for c in name if c in "aeiou") / max(len(name), 1),
        "consonant_ratio": sum(1 for c in name if c not in "aeiou") / max(len(name), 1),
        "has_repeated_letters": int(len(name) != len(set(name))),
        "unique_chars": len(set(name)),
    }
    return features


def _word_count(domain: str) -> int:
    name = domain.replace(".com", "").lower()
    return len(re.findall(r"[a-z]{2,}", name))


def _compute_similarity(d1_features: dict, d2_features: dict) -> float:
    """Cosine-like similarity between two domain feature vectors."""
    keys = set(d1_features.keys()) & set(d2_features.keys())
    if not keys:
        return 0.0
    dot = sum(d1_features[k] * d2_features[k] for k in keys)
    norm1 = np.linalg.norm([d1_features[k] for k in keys])
    norm2 = np.linalg.norm([d2_features[k] for k in keys])
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


def update_investor_profile() -> None:
    """Analyze feedback history and update the investor profile weights."""
    history = get_feedback_history()
    if not history:
        logger.info("No feedback history – skipping profile update")
        return

    liked = [h for h in history if h["rating"] in ("BUY", "GOOD")]
    disliked = [h for h in history if h["rating"] in ("BAD", "SKIP")]

    if not liked:
        logger.info("No liked domains yet – skipping profile update")
        return

    # Compute average metrics for liked domains
    avg_features = {}
    for feat in FEATURES:
        values = [h.get(feat, 50) for h in liked if h.get(feat) is not None]
        if values:
            avg_features[feat] = np.mean(values)
        else:
            avg_features[feat] = 50.0

    # Compute importance: liked vs disliked contrast
    for feat in FEATURES:
        liked_vals = [h.get(feat, 50) for h in liked if h.get(feat) is not None]
        disliked_vals = [h.get(feat, 50) for h in disliked if h.get(feat) is not None]

        if liked_vals and disliked_vals:
            contrast = abs(np.mean(liked_vals) - np.mean(disliked_vals))
            importance = min(1.0, contrast / 50.0)
        elif liked_vals:
            importance = 0.5
        else:
            importance = 0.0

        # Weight is the average feature value weighted by importance
        weight = round(avg_features.get(feat, 50) * (0.5 + importance * 0.5), 2)

        if importance > 0.3:
            importance_label = "high"
        elif importance > 0.1:
            importance_label = "medium"
        else:
            importance_label = "low"

        upsert_investor_profile(feat, weight, importance_label)

    logger.info("Investor profile updated from %d feedback entries", len(history))


def adjust_score_with_profile(domain_data: dict) -> float:
    """
    Adjust a domain's final score based on the learned investor profile.
    Returns an adjusted score (bonus or penalty).
    """
    profile = get_investor_profile()
    if not profile:
        return 0.0

    adjustment = 0.0
    total_weight = 0.0

    for feat in FEATURES:
        profile_weight = profile.get(feat, 0.0)
        if profile_weight == 0:
            continue

        domain_val = domain_data.get(feat, 50)
        # If the profile likes higher values of this feature, reward alignment
        # Normalize: score proximity
        diff = abs(domain_val - profile_weight) / 100.0
        alignment = 1.0 - min(diff, 1.0)
        adjustment += alignment * (profile_weight / 50.0) * 10.0
        total_weight += 1.0

    if total_weight == 0:
        return 0.0

    return round(adjustment / total_weight, 2)


def find_similar_domains(domain: str, top_n: int = 10) -> list[dict]:
    """Find previously scored domains similar to the given domain."""
    from database import get_previous_top_domains

    target_feats = _domain_features(domain)
    candidates = get_previous_top_domains(limit=500)

    scored = []
    for c in candidates:
        c_feats = _domain_features(c["domain"])
        sim = _compute_similarity(target_feats, c_feats)
        scored.append((sim, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for s, c in scored[:top_n] if s > 0.3]


def get_preference_summary() -> str:
    """Generate a human-readable summary of the investor profile."""
    profile = get_investor_profile()
    if not profile:
        return "No preference data yet."

    lines = ["Investor Preference Profile:", "----------------------------"]
    for feat in sorted(profile.keys()):
        val = profile[feat]
        lines.append(f"  {feat}: {val:.1f}")

    history = get_feedback_history()
    ratings = Counter(h["rating"] for h in history)
    lines.append("")
    lines.append(f"Total ratings: {len(history)}")
    lines.append(f"  BUY:  {ratings.get('BUY', 0)}")
    lines.append(f"  GOOD: {ratings.get('GOOD', 0)}")
    lines.append(f"  BAD:  {ratings.get('BAD', 0)}")
    lines.append(f"  SKIP: {ratings.get('SKIP', 0)}")
    return "\n".join(lines)
