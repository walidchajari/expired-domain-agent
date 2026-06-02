import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Brandable",
    "Geo Domain",
    "AI Domain",
    "Fintech Domain",
    "SaaS Domain",
    "E-commerce Domain",
    "Health Domain",
    "Travel Domain",
    "Generic Keyword Domain",
    "Local Business Domain",
]

# ---------------------------------------------------------------------------
# Geo data
# ---------------------------------------------------------------------------

MAJOR_CITIES = {
    "miami", "texas", "casablanca", "marrakech", "florida", "dallas", "houston",
    "newyork", "newyorkcity", "nyc", "losangeles", "la", "chicago", "sanfrancisco",
    "sf", "seattle", "boston", "denver", "austin", "portland", "nashville",
    "atlanta", "phoenix", "philadelphia", "sandiego", "minneapolis", "detroit",
    "orlando", "charlotte", "raleigh", "sacramento", "tampa", "stlouis",
    "pittsburgh", "cincinnati", "cleveland", "indianapolis", "columbus",
    "kansascity", "milwaukee", "lasvegas", "vegas", "oakland", "memphis",
    "louisville", "baltimore", "richmond", "neworleans", "nola", "saltlakecity",
    "albuquerque", "tucson", "fresno", "longbeach", "virginiabeach",
    "london", "paris", "berlin", "madrid", "rome", "milan", "barcelona",
    "amsterdam", "brussels", "vienna", "munich", "hamburg", "dublin",
    "stockholm", "oslo", "helsinki", "copenhagen", "prague", "warsaw",
    "budapest", "lisbon", "athens", "istanbul", "moscow", "dubai", "abudhabi",
    "doha", "riyadh", "jeddah", "telaviv", "jerusalem", "cairo", "casablanca",
    "tunis", "algiers", "rabat", "nairobi", "lagos", "capetown", "johannesburg",
    "durban", "accra", "casablanca", "marrakech", "fes", "tangier",
    "tokyo", "osaka", "kyoto", "yokohama", "nagoya", "sapporo",
    "seoul", "busan", "incheon",
    "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou",
    "hongkong", "hk", "taipei", "kaohsiung",
    "mumbai", "delhi", "newdelhi", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "ahmedabad", "jaipur",
    "bangkok", "phuket", "pattaya", "chiangmai",
    "singapore", "kualalumpur", "jakarta", "bali", "manila", "hanoi",
    "hochiminh", "saigon", "hcmc", "yangon", "phnompenh",
    "sydney", "melbourne", "brisbane", "perth", "adelaide", "goldcoast",
    "auckland", "wellington", "christchurch",
    "toronto", "vancouver", "montreal", "calgary", "ottawa", "edmonton",
    "winnipeg", "quebec", "hamilton",
    "mexicocity", "cancun", "guadalajara", "monterrey", "tijuana",
    "saopaulo", "riodejaneiro", "brasilia", "salvador", "fortaleza",
    "buenosaires", "santiago", "lima", "bogota", "caracas", "montevideo",
    "lagos", "cairo", "alexandria", "giza", "sharm", "luxor",
    "marrakech", "rabat", "fes", "tangier", "oujda", "kenitra",
}

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "newhampshire", "newjersey", "newmexico", "newyork", "northcarolina",
    "northdakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhodeisland", "southcarolina", "southdakota", "tennessee", "texas",
    "utah", "vermont", "virginia", "washington", "westvirginia",
    "wisconsin", "wyoming",
}

COUNTRIES = {
    "usa", "america", "canada", "mexico", "uk", "england", "scotland",
    "france", "germany", "italy", "spain", "portugal", "netherlands",
    "belgium", "switzerland", "austria", "sweden", "norway", "denmark",
    "finland", "poland", "czech", "greece", "turkey", "uae", "egypt",
    "morocco", "tunisia", "algeria", "nigeria", "kenya", "southafrica",
    "china", "japan", "korea", "india", "thailand", "vietnam", "indonesia",
    "philippines", "australia", "newzealand", "brazil", "argentina",
}

LOCAL_SERVICE_KEYWORDS = {
    "roofing", "roof", "hvac", "plumbing", "plumber", "electric", "electrician",
    "cleaning", "lawn", "landscaping", "pest", "locksmith", "moving", "mover",
    "remodeling", "renovation", "contractor", "construction", "builder",
    "painting", "painter", "carpet", "flooring", "tile", "window", "door",
    "garage", "fencing", "deck", "patio", "pool", "spa", "septic", "well",
    "water", "heating", "cooling", "ac", "appliance", "repair", "service",
    "handyman", "maintenance", "inspection", "install", "installation",
    "solar", "generator", "security", "alarm", "cctv",
    "dentist", "dental", "clinic", "doctor", "chiropractor", "massage",
    "spa", "salon", "barber", "nails", "yoga", "fitness", "gym",
    "lawyer", "attorney", "law", "legal", "notary", "insurance", "agent",
    "realtor", "realestate", "property", "rental", "apartment", "condo",
}

# ---------------------------------------------------------------------------
# Industry / category keyword lists
# ---------------------------------------------------------------------------

AI_KEYWORDS = {
    "ai", "artificial", "intelligence", "smart", "brain", "mind", "neural",
    "deep", "learn", "ml", "gpt", "chat", "bot", "automate", "cognitive",
    "vision", "voice", "speech", "nlp", "llm", "agent", "assist", "genai",
    "generative", "predict", "analytics", "insight", "data", "algorithm",
    "model", "train", "infer", "reason", "think", "augment", "sentient",
    "machine", "robot", "drone", "autonomous", "cyber", "compute",
}

FINTECH_KEYWORDS = {
    "pay", "payment", "cash", "bank", "fin", "finance", "financial", "invest",
    "wealth", "capital", "fund", "trade", "stock", "market", "coin", "crypto",
    "blockchain", "bitcoin", "token", "wallet", "credit", "debit", "card",
    "loan", "mortgage", "insure", "insurance", "tax", "account", "money",
    "dollar", "euro", "forex", "bond", "equity", "venture", "fintech",
}

SAAS_KEYWORDS = {
    "app", "cloud", "hub", "io", "saas", "soft", "software", "platform",
    "suite", "tool", "kit", "api", "sync", "flow", "workflow", "automate",
    "manage", "dashboard", "analytics", "insight", "metric", "report",
    "collab", "team", "project", "task", "track", "crm", "erp", "hr",
    "payroll", "inventory", "invoice", "billing", "subscription",
}

ECOMMERCE_KEYWORDS = {
    "shop", "buy", "cart", "store", "market", "mall", "deal", "save",
    "price", "coupon", "discount", "offer", "sell", "sale", "order",
    "checkout", "delivery", "ship", "shipping", "return", "refund",
    "product", "catalog", "vendor", "seller", "merchant", "retail",
    "wholesale", "trade", "auction", "bid", "ecom", "ecommerce", "boutique",
    "goods", "mart", "bazaar", "emporium",
}

HEALTH_KEYWORDS = {
    "health", "care", "med", "medical", "doctor", "dr", "hospital", "clinic",
    "pharma", "drug", "wellness", "fitness", "nutrition", "diet", "vitamin",
    "supplement", "therapy", "therapist", "mental", "brain", "body", "muscle",
    "weight", "loss", "skin", "hair", "beauty", "cosmetic", "surgery",
    "dental", "vision", "eye", "ear", "heart", "bone", "joint", "pain",
    "relief", "sleep", "rehab", "nurse", "patient", "cure", "heal",
}

TRAVEL_KEYWORDS = {
    "travel", "tour", "trip", "fly", "flight", "air", "airline", "plane",
    "jet", "voyage", "cruise", "sail", "boat", "ship", "hotel", "resort",
    "hostel", "inn", "lodge", "vacation", "holiday", "getaway", "escape",
    "adventure", "explore", "discover", "wander", "roam", "trek", "hike",
    "map", "guide", "tourist", "destination", "beach", "mountain", "lake",
    "island", "city", "visit", "go", "ride", "drive", "rental", "car",
    "booking", "reservation",
}

SUCCESSFUL_STARTUPS = {
    "stripe", "uber", "openai", "notion", "klarna", "figma", "slack",
    "zoom", "shopify", "spotify", "twitter", "snapchat", "tiktok",
    "netflix", "airbnb", "doordash", "robinhood", "pinterest", "flickr",
    "venmo", "square", "stripe", "discord", "twilio", "sendgrid",
    "datadog", "mongodb", "dropbox", "asana", "canva", "trello",
    "invision", "abstract", "vercel", "netlify", "render", "railway",
    "planetscale", "neon", "supabase", "flyio", "replit", "codepen",
    "codesandbox", "linear", "height", "superhuman", "arcane", "deel",
    "brex", "chime", "plaid", "affirm", "stash", "acorns", "betterment",
    "wealthfront", "sofi", "monzo", "revolut", "nubank", "niubiz",
    "wyre", "alchemy", "infura", "quicknode", "chainlink", "polygon",
    "avalanche", "near", "sui", "aptos", "solana", "cosmos", "celestia",
}

# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

VOWELS = set("aeiou")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def _is_cvcvcv(name: str) -> bool:
    if len(name) != 6:
        return False
    return (name[0] in CONSONANTS and name[1] in VOWELS and
            name[2] in CONSONANTS and name[3] in VOWELS and
            name[4] in CONSONANTS and name[5] in VOWELS)


def _is_cvvcv(name: str) -> bool:
    if len(name) != 5:
        return False
    return (name[0] in CONSONANTS and name[1] in VOWELS and
            name[2] in VOWELS and name[3] in CONSONANTS and
            name[4] in VOWELS)


def _is_vcvcv(name: str) -> bool:
    if len(name) != 5:
        return False
    return (name[0] in VOWELS and name[1] in CONSONANTS and
            name[2] in VOWELS and name[3] in CONSONANTS and
            name[4] in VOWELS)


def _vowel_ratio(name: str) -> float:
    if not name:
        return 0
    return sum(1 for c in name if c in VOWELS) / len(name)


def _consonant_ratio(name: str) -> float:
    if not name:
        return 0
    return sum(1 for c in name if c in CONSONANTS) / len(name)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_domain(domain: str) -> str:
    name = domain.replace(".com", "").lower()
    if not name:
        return "Generic Keyword Domain"

    scores = {cat: 0.0 for cat in CATEGORIES}

    ai_kw = sum(1 for kw in AI_KEYWORDS if kw in name)
    fintech_kw = sum(1 for kw in FINTECH_KEYWORDS if kw in name)
    saas_kw = sum(1 for kw in SAAS_KEYWORDS if kw in name)
    ecom_kw = sum(1 for kw in ECOMMERCE_KEYWORDS if kw in name)
    health_kw = sum(1 for kw in HEALTH_KEYWORDS if kw in name)
    travel_kw = sum(1 for kw in TRAVEL_KEYWORDS if kw in name)

    has_geo = name in MAJOR_CITIES or name in US_STATES or name in COUNTRIES
    city_match = _find_geo_in_name(name)
    local_kw = sum(1 for kw in LOCAL_SERVICE_KEYWORDS if kw in name)
    is_brandable_pattern = _is_cvcvcv(name) or _is_cvvcv(name) or _is_vcvcv(name)

    scores["AI Domain"] = ai_kw * 20
    scores["Fintech Domain"] = fintech_kw * 20
    scores["SaaS Domain"] = saas_kw * 20
    scores["E-commerce Domain"] = ecom_kw * 20
    scores["Health Domain"] = health_kw * 20
    scores["Travel Domain"] = travel_kw * 20

    if city_match and local_kw > 0:
        scores["Local Business Domain"] = 40 + (local_kw * 15) + (city_match[1] * 10)
    if has_geo:
        scores["Geo Domain"] = 50
    if city_match and local_kw == 0:
        scores["Geo Domain"] = max(scores["Geo Domain"], 30 + city_match[1] * 10)

    if is_brandable_pattern:
        scores["Brandable"] = 60 + (10 if 5 <= len(name) <= 8 else 0)
    elif 4 <= len(name) <= 9 and not re.search(r"\d", name) and "-" not in name:
        if _vowel_ratio(name) >= 0.35:
            scores["Brandable"] = 40

    if not any(v > 20 for v in scores.values()):
        scores["Generic Keyword Domain"] = 30

    best = max(scores, key=scores.get)
    return best


def _find_geo_in_name(name: str) -> Optional[tuple[str, int]]:
    for length in range(min(len(name), 20), 2, -1):
        for start in range(len(name) - length + 1):
            substr = name[start:start + length]
            if substr in MAJOR_CITIES:
                return (substr, 3)
            if substr in US_STATES:
                return (substr, 2)
            if substr in COUNTRIES:
                return (substr, 1)
    return None


# ---------------------------------------------------------------------------
# Geo scoring
# ---------------------------------------------------------------------------


def compute_geo_score(domain: str) -> int:
    name = domain.replace(".com", "").lower()
    score = 0

    geo_match = _find_geo_in_name(name)
    if geo_match:
        geo_word, priority = geo_match
        score += priority * 15
        if geo_word in MAJOR_CITIES:
            score += 20
            for kw in LOCAL_SERVICE_KEYWORDS:
                if kw in name and kw != geo_word:
                    score += 15
                    break
        elif geo_word in US_STATES:
            score += 15
            for kw in LOCAL_SERVICE_KEYWORDS:
                if kw in name and kw != geo_word:
                    score += 10
                    break
        elif geo_word in COUNTRIES:
            score += 10

    if any(kw in name for kw in {"roofing", "hvac", "plumbing", "electric", "roof",
                                  "cleaning", "pest", "locksmith", "moving", "mover",
                                  "contractor", "dentist", "lawyer", "realtor", "loan",
                                  "insurance", "solar", "remodeling"}):
        score += 10

    if score > 0:
        score += 10

    return min(100, score)


# ---------------------------------------------------------------------------
# Brandable scoring
# ---------------------------------------------------------------------------

def compute_brandability_score(domain: str, existing_brandability: int = 50) -> int:
    name = domain.replace(".com", "").lower()
    score = existing_brandability

    if len(name) < 3 or len(name) > 12:
        score = max(0, score - 20)
    elif 5 <= len(name) <= 8:
        score += 15
    elif len(name) in (4, 9):
        score += 5

    if _is_cvcvcv(name):
        score += 25
    elif _is_cvvcv(name):
        score += 20
    elif _is_vcvcv(name):
        score += 15

    vr = _vowel_ratio(name)
    if 0.35 <= vr <= 0.55:
        score += 10
    elif vr > 0.55:
        score += 5

    if re.search(r"(.)\1", name):
        score -= 5
    if re.search(r"\d", name):
        score -= 30
    if "-" in name:
        score -= 25

    if len(set(name)) >= len(name) * 0.7:
        score += 5

    for startup in SUCCESSFUL_STARTUPS:
        if startup in name:
            score += 10
            break

    if name.endswith("ify") or name.endswith("ly") or name.endswith("io"):
        score += 10
    if name.endswith("hub") or name.endswith("lab") or name.endswith("ix"):
        score += 8

    if len(name) >= 3 and name[-1] in VOWELS:
        score += 5

    return min(100, max(0, score))


# ---------------------------------------------------------------------------
# Price estimation
# ---------------------------------------------------------------------------

def estimate_end_user_price(domain: str, final_score: float, category: str, geo_score: int, brand_score: int) -> str:
    if final_score >= 90:
        return "$5,000 - $15,000"
    elif final_score >= 80:
        return "$1,000 - $5,000"
    elif final_score >= 70:
        return "$500 - $1,000"
    elif final_score >= 60:
        return "$250 - $500"
    else:
        return "$50 - $250"


def estimate_wholesale_price(domain: str, final_score: float, category: str, geo_score: int, brand_score: int) -> str:
    if final_score >= 90:
        return "$1,000 - $3,000"
    elif final_score >= 80:
        return "$300 - $1,000"
    elif final_score >= 70:
        return "$150 - $300"
    elif final_score >= 60:
        return "$75 - $150"
    else:
        return "$20 - $75"


def estimate_probability_of_sale(final_score: float) -> float:
    if final_score >= 90:
        return 85.0
    elif final_score >= 80:
        return 65.0
    elif final_score >= 70:
        return 45.0
    elif final_score >= 60:
        return 25.0
    else:
        return 10.0


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze_domain(domain_data: dict) -> dict:
    domain = domain_data["domain"]
    name = domain.replace(".com", "").lower()
    final_score = domain_data.get("final_score", 50)

    category = classify_domain(domain)
    geo_score = compute_geo_score(domain)
    brand_score = compute_brandability_score(domain, domain_data.get("brandability", 50))

    end_user = estimate_end_user_price(domain, final_score, category, geo_score, brand_score)
    wholesale = estimate_wholesale_price(domain, final_score, category, geo_score, brand_score)
    prob_sale = estimate_probability_of_sale(final_score)

    return {
        "domain": domain,
        "category": category,
        "geo_score": geo_score,
        "brandability_score": brand_score,
        "estimated_end_user_price": end_user,
        "estimated_wholesale_price": wholesale,
        "probability_of_sale": prob_sale,
    }


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def generate_rankings(scored_domains: list[dict]) -> dict:
    analyzed = [analyze_domain(d) for d in scored_domains]

    for ad in analyzed:
        for sd in scored_domains:
            if sd["domain"] == ad["domain"]:
                sd.update(ad)
                break

    overall = sorted(scored_domains, key=lambda x: x.get("final_score", 0), reverse=True)[:20]

    brandable = sorted(
        [d for d in scored_domains if d.get("category") == "Brandable"],
        key=lambda x: x.get("brandability_score", 0),
        reverse=True,
    )[:20]

    geo = sorted(
        [d for d in scored_domains if d.get("geo_score", 0) > 0],
        key=lambda x: x.get("geo_score", 0),
        reverse=True,
    )[:20]

    return {
        "overall": overall,
        "brandable": brandable,
        "geo": geo,
    }
