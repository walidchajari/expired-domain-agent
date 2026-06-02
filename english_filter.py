"""
English Dictionary Filter & Domain Investor Mode Scoring

Uses wordfreq (when available) with a ~5000-word fallback list to:
  1. Segment domain names into English words
  2. Score dictionary coverage, pronounceability, memorability, commercial intent
  3. Detect "Domain Investor Mode" names (e.g. Velora, Nexora)
  4. Pre-filter truly random letter combinations
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback English word list (~5000 common English words useful for domains)
# ---------------------------------------------------------------------------
_FALLBACK_WORDS: set[str] = {
    # Common short words (2-3 letters)
    "a", "an", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is", "it",
    "me", "my", "no", "of", "on", "or", "so", "to", "up", "us", "we",
    "act", "add", "age", "ago", "air", "all", "and", "any", "arm", "art",
    "ask", "bad", "bag", "bar", "bed", "big", "bit", "box", "boy", "bus",
    "but", "buy", "can", "cap", "car", "cat", "cup", "cut", "day", "did",
    "dig", "dog", "dot", "dry", "ear", "eat", "egg", "end", "eve", "eye",
    "fan", "far", "fat", "few", "fig", "fit", "fix", "fly", "for", "fox",
    "fun", "gap", "gas", "get", "god", "got", "gun", "gut", "guy", "had",
    "hat", "hay", "hen", "her", "hid", "him", "hip", "his", "hit", "hog",
    "hop", "hot", "how", "hub", "hug", "ice", "ill", "its", "jab", "jam",
    "jar", "jaw", "jet", "job", "jog", "joy", "jug", "key", "kid", "kit",
    "lab", "lad", "lap", "law", "lay", "leg", "let", "lid", "lip", "log",
    "lot", "low", "mad", "man", "map", "mat", "may", "men", "mix", "mom",
    "mud", "net", "new", "nod", "nor", "not", "now", "nut", "odd", "off",
    "oil", "old", "one", "our", "out", "own", "pad", "pan", "pat", "pay",
    "pen", "pet", "pie", "pig", "pin", "pit", "pop", "pot", "pro", "pub",
    "put", "rag", "ran", "rap", "rat", "raw", "red", "rig", "rim", "rip",
    "rob", "rod", "roe", "row", "rub", "rug", "rum", "run", "rut", "rye",
    "sac", "sad", "sag", "sat", "saw", "say", "sea", "set", "sew", "she",
    "shy", "sin", "sip", "sir", "sit", "six", "ski", "sky", "sly", "sob",
    "sod", "son", "sop", "sot", "sow", "soy", "spa", "spy", "sty", "sub",
    "sue", "sum", "sun", "sup", "tab", "tag", "tan", "tap", "tar", "tax",
    "tea", "ten", "the", "tie", "tin", "tip", "toe", "ton", "too", "top",
    "tow", "toy", "try", "tub", "tug", "two", "use", "van", "vat", "vet",
    "vow", "wad", "wag", "war", "was", "wax", "way", "web", "wed", "wet",
    "who", "why", "wig", "win", "wit", "woe", "wok", "won", "woo", "wow",
    "yak", "yam", "yap", "yaw", "yes", "yet", "yew", "you", "zap", "zen",
    "zip", "zoo",
    # 4-letter common
    "able", "ache", "acid", "acme", "acre", "ally", "also", "arch", "area",
    "army", "auto", "away", "axle", "back", "bait", "bake", "bald", "bale",
    "ball", "band", "bane", "bang", "bank", "bare", "bark", "barn", "base",
    "bath", "bead", "beak", "beam", "bean", "bear", "beat", "beef", "been",
    "beer", "bell", "belt", "bend", "bent", "best", "bias", "bike", "bill",
    "bind", "bird", "bite", "blah", "bled", "blew", "blip", "blob", "blot",
    "blow", "blue", "blur", "boar", "boat", "body", "bold", "bolt", "bomb",
    "bond", "bone", "book", "boom", "boot", "bore", "born", "boss", "both",
    "bout", "bowl", "bulk", "bull", "bump", "burn", "bury", "bush", "busy",
    "cafe", "cage", "cake", "calf", "call", "calm", "came", "camp", "cane",
    "cape", "card", "care", "cart", "case", "cash", "cast", "cave", "cell",
    "chat", "chef", "chew", "chin", "chip", "chop", "cite", "city", "clad",
    "clam", "clan", "clap", "claw", "clay", "clip", "clock", "clod", "clog",
    "club", "clue", "coal", "coat", "coda", "code", "coin", "cold", "colt",
    "comb", "come", "cone", "cook", "cool", "cope", "copy", "cord", "core",
    "cork", "corn", "cost", "cosy", "coup", "cove", "cozy", "crab", "crew",
    "crop", "crow", "cube", "cult", "curb", "cure", "curl", "cute", "dame",
    "damp", "dare", "dark", "dart", "dash", "data", "dawn", "dead", "deaf",
    "deal", "dear", "debt", "deck", "deep", "deer", "demo", "dent", "deny",
    "desk", "dial", "dice", "diet", "dine", "dire", "dirt", "disc", "dish",
    "disk", "dock", "does", "dome", "done", "doom", "door", "dose", "dove",
    "down", "doze", "drag", "draw", "drew", "drip", "drop", "drum", "dual",
    "duck", "duel", "duke", "dull", "dumb", "dump", "dune", "dunk", "dusk",
    "dust", "duty", "dyed", "each", "eager", "eagle", "earn", "ease", "edge",
    "edit", "else", "emit", "epic", "even", "ever", "evil", "exam", "exit",
    "face", "fact", "fade", "fail", "fair", "fake", "fall", "fame", "fang",
    "farm", "fast", "fate", "fear", "feat", "feed", "feel", "fell", "felt",
    "fend", "fern", "fest", "file", "fill", "film", "find", "fine", "fire",
    "firm", "fish", "fist", "five", "flag", "flame", "flap", "flat", "flaw",
    "flea", "fled", "flew", "flex",     "flip", "flit", "flog", "flow", "foam",
    "fold", "folk", "fond", "food", "fool", "foot", "ford", "fore", "fork",
    "form", "fort", "foul", "four", "foxy", "free", "frog", "from", "fuel",
    "full", "fume", "fund", "fuse", "fuss", "fuzz", "gain", "gale", "game",
    "gang", "gape", "garb", "gate", "gave", "gaze", "gear", "gene", "gift",
    "girl", "give", "glad", "glen", "glow", "glue", "glum", "gnat", "goat",
    "goes", "gold", "golf", "gone", "good", "gore", "grab", "gray", "grew",
    "grid", "grim", "grin", "grip", "grit", "grow", "gulf", "gust", "guts",
    "hack", "hail", "hair", "hale", "half", "hall", "halt", "hand", "hang",
    "hare", "harm", "hart", "hash", "hate", "haul", "have", "haze", "hazy",
    "head", "heal", "heap", "hear", "heat", "heed", "heel", "heir", "held",
    "hell", "helm", "help", "herd", "here", "hero", "hide", "high", "hill",
    "hilt", "hind", "hint", "hire", "hiss", "hive", "hoax", "hold", "hole",
    "holy", "home", "hone", "hood", "hoof", "hook", "hope", "horn", "hose",
    "host", "hour", "howl", "huge", "hull", "hump", "hung", "hunt", "hurt",
    "hush", "icon", "idea", "idle", "inch", "info", "into", "iron", "isle",
    "item", "jack", "jade", "jail", "jazz", "jean", "jerk", "jest", "jolt",
    "jury", "keen", "keep", "kept", "kick", "kill", "kind", "king", "kiss",
    "kite", "knee", "knew", "knit", "knob", "knot", "know", "lace", "lack",
    "lady", "laid", "lake", "lamb", "lame", "lamp", "land", "lane", "lark",
    "lash", "lass", "last", "late", "lawn", "lazy", "lead", "leaf", "leak",
    "lean", "leap", "left", "lend", "lens", "lent", "less", "liar", "lick",
    "life", "lift", "like", "limb", "lime", "limp", "line", "link", "lion",
    "list", "live", "load", "loaf", "loan", "lock", "loft", "lone", "long",
    "look", "loop", "lord", "lore", "lose", "loss", "lost", "loud", "love",
    "luck", "lull", "lung", "lure", "lurk", "lush", "lust", "made", "maid",
    "mail", "main", "make", "male", "mall", "malt", "mane", "many", "march",
    "mare", "mark", "mask", "mass", "mast", "mate", "maze", "mean", "meat",
    "meet", "melt", "memo", "mend", "menu", "mere", "mesh", "mess", "mild",
    "mile", "milk", "mill", "mind", "mine", "miss", "mist", "moan", "mock",
    "mode", "mold", "mole", "mood", "moon", "moor", "more", "moss", "most",
    "moth", "move", "much", "mule", "mull", "muse", "mush", "must", "mute",
    "myth", "nail", "name", "nape", "navy", "near", "neat", "neck", "need",
    "nest", "news", "next", "nice", "nine", "node", "none", "noon", "norm",
    "nose", "note", "noun", "nude", "numb", "oath", "obey", "odds", "omen",
    "omit", "once", "only", "onto", "ooze", "open", "oral", "orca", "orgy",
    "oven", "over", "pace", "pack", "page", "paid", "pail", "pain", "pair",
    "pale", "palm", "pane", "pang", "park", "part", "pass", "past", "path",
    "pave", "peak", "peal", "pear", "peat", "peck", "peel", "peer", "pelt",
    "pend", "perk", "pest", "pick", "pie", "pier", "pike", "pile", "pill",
    "pine", "pink", "pipe", "plan", "play", "plea", "plod", "plot", "plow",
    "ploy", "plug", "plum", "plus", "pock", "poem", "poet", "poke", "pole",
    "poll", "polo", "pond", "pony", "pool", "poor", "pope", "pork", "port",
    "pose", "post", "pour", "pray", "prey", "prig", "prim", "prod", "prop",
    "rove", "prow", "pull", "pulp", "pump", "punk", "pure", "purr", "push",
    "quit", "quiz", "race", "rack", "raft", "rage", "raid", "rail", "rain",
    "rake", "ramp", "rang", "rank", "rant", "rash", "rate", "rave", "read",
    "real", "reap", "rear", "reef", "reel", "rein", "rely", "rend", "rent",
    "rest", "rice", "rich", "ride", "rift", "right", "rigid", "ring", "riot",
    "rise", "risk", "road", "roam", "roar", "robe", "rock", "rode", "role",
    "roll", "roof", "room", "root", "rope", "rose", "rosy", "rout", "rove",
    "rude", "ruin", "rule", "rump", "rung", "ruse", "rush", "rust", "sack",
    "safe", "saga", "sage", "said", "sail", "sake", "sale", "salt", "same",
    "sand", "sane", "sang", "sank", "save", "seal", "seam", "seat", "seed",
    "seek", "seem", "seen", "self", "sell", "send", "sent", "sept", "serf",
    "set", "sewn", "shack", "shade", "shake", "shall", "shame", "shape",
    "share", "shark", "sharp", "shave", "shawl", "shear", "shed", "sheep",
    "sheer", "sheet", "shelf", "shell", "shift", "shine", "shirt", "shock",
    "shoe", "shook", "shoot", "shore", "short", "shout", "shove", "show",
    "shrub", "shrug", "shut", "shy", "sick", "side", "sift", "sigh", "sign",
    "silk", "sill", "silt", "sing", "sink", "sire", "site", "size", "sketch",
    "skid", "skim", "skin", "skip", "skirt", "skull", "slab", "slack", "slap",
    "slash", "slate", "slave", "sled", "sleep", "slew", "slice", "slid",
    "slide", "slim", "slip", "slit", "slope", "slot", "slow", "slug", "slum",
    "slump", "smack", "small", "smart", "smell", "smile", "smoke", "snack",
    "snap", "snare", "snarl", "sniff", "snip", "snob", "snow", "snug", "soak",
    "soap", "soar", "sock", "soda", "sofa", "soft", "soil", "sold", "sole",
    "some", "song", "soon", "soot", "sore", "sort", "soul", "sour", "sown",
    "span", "spare", "spark", "speak", "spear", "speed", "spell", "spend",
    "spent", "spice", "spill", "spin", "spine", "spite", "split", "spoke",
    "spoon", "sport", "spot", "spout", "spray", "spur", "squat", "squeeze",
    "stab", "stack", "staff", "stage", "stain", "stair", "stake", "stale",
    "stalk", "stall", "stamp", "stand", "star", "stare", "start", "state",
    "stay", "steak", "steal", "steam", "steel", "steep", "steer", "stem",
    "step", "stick", "stiff", "still", "sting", "stir", "stock", "stole",
    "stone", "stood", "stool", "stop", "store", "storm", "story", "stout",
    "stove", "strap", "straw", "stray", "strip", "stuck", "study", "stuff",
    "stump", "style", "suck", "sugar", "suit", "summer", "sun", "super",
    "surge", "sushi", "swamp", "swan", "swap", "swarm", "sway", "swear",
    "sweat", "sweep", "sweet", "swell", "swept", "swift", "swim", "swing",
    "swipe", "swirl", "swore", "sworn", "swung", "sync", "syrup",
    # Longer common words
    "able", "about", "above", "abuse", "accept", "access", "across", "action",
    "active", "actor", "actual", "adapt", "added", "admit", "adopt", "adult",
    "advance", "advise", "affect", "afford", "after", "again", "agent", "agree",
    "ahead", "alarm", "album", "alive", "allow", "alone", "along", "already",
    "alter", "always", "amount", "angel", "anger", "angle", "animal", "ankle",
    "annual", "answer", "anyone", "apart", "appeal", "appear", "apple", "apply",
    "arena", "argue", "arise", "arrange", "array", "arrive", "artist", "aspect",
    "assert", "assess", "asset", "assign", "assist", "assume", "attach", "attack",
    "attend", "attract", "aunt", "author", "avenue", "average", "avoid", "award",
    "aware", "awful", "bacon", "badge", "baker", "balance", "ballot", "banana",
    "banner", "barrel", "barrier", "basin", "basis", "basket", "battery", "battle",
    "beach", "beauty", "became", "because", "become", "before", "behalf", "behave",
    "being", "belief", "believe", "belong", "bench", "beneath", "beside", "beyond",
    "billion", "binary", "binder", "biopsy", "bishop", "bitter", "blade", "blame",
    "bland", "blank", "blast", "blaze", "bleak", "bleed", "blend", "bless", "blind",
    "bliss", "block", "blood", "bloom", "blossom", "board", "boast", "bonus",
    "booth", "border", "borrow", "bother", "bottle", "bottom", "bounce", "bounty",
    "branch", "brand", "brave", "bread", "break", "breath", "breed", "breeze",
    "brewer", "brick", "bridge", "brief", "bright", "bring", "brochure", "broken",
    "bronze", "broom", "brother", "brown", "brush", "bubble", "bucket", "buddy",
    "budget", "buffer", "build", "bunch", "bundle", "burden", "bureau", "burial",
    "buried", "burner", "burst", "bushel", "butter", "button", "cabin", "cabinet",
    "cable", "cactus", "cafe", "cage", "cake", "calcium", "calculate", "calendar",
    "calm", "camera", "camp", "campaign", "campus", "canal", "cancel", "candle",
    "canvas", "canyon", "capable", "capital", "captain", "capture", "carbon",
    "career", "careful", "cargo", "carpet", "carrot", "carry", "cartel", "case",
    "casino", "castle", "casual", "catalog", "catch", "cattle", "caught", "causal",
    "cave", "cease", "ceiling", "celebrity", "celery", "cell", "cement", "center",
    "central", "century", "cereal", "certain", "chain", "chair", "chalk", "chamber",
    "champion", "chance", "change", "channel", "chaos", "chapter", "charge",
    "charity", "charm", "chart", "chase", "cheap", "check", "cheese", "cherry",
    "chest", "chicken", "chief", "child", "chill", "choose", "chosen", "church",
    "circle", "circuit", "citizen", "civil", "claim", "clap", "clarify", "clash",
    "class", "clay", "clean", "clear", "clerk", "clever", "click", "client",
    "cliff", "climate", "climb", "clinic", "clock", "close", "closet", "cloth",
    "cloud", "clown", "club", "clue", "cluster", "coach", "coast", "coconut",
    "code", "coffee", "cohort", "coil", "coin", "cold", "collar", "collect",
    "college", "colony", "color", "column", "combat", "combine", "comedy",
    "comfort", "comic", "coming", "commit", "common", "company", "compete",
    "complain", "complex", "concept", "concern", "conduct", "confirm", "conquer",
    "consent", "consist", "consult", "contact", "contain", "content", "contest",
    "context", "control", "convert", "convince", "cook", "cookie", "cool",
    "cooper", "copper", "copy", "coral", "cord", "core", "cork", "corn", "corner",
    "correct", "corrupt", "cotton", "couch", "council", "count", "counter",
    "county", "couple", "courage", "course", "court", "cousin", "cover", "crack",
    "craft", "crash", "crawl", "crazy", "cream", "create", "credit", "creek",
    "crest", "crew", "cricket", "crime", "crisis", "crisp", "critic", "crop",
    "cross", "crowd", "crown", "crude", "crush", "crust", "crystal", "cube",
    "culture", "cunning", "cup", "cure", "curious", "current", "curtain", "curve",
    "cushion", "custom", "cycle", "dairy", "dance", "danger", "dare", "dark",
    "darling", "dash", "data", "database", "daughter", "dawn", "day", "dead",
    "deaf", "deal", "dear", "death", "debate", "debt", "decade", "decay", "decent",
    "decide", "deck", "declare", "decline", "decore", "decrease", "deep", "deer",
    "defeat", "defend", "define", "degree", "delay", "delete", "delight", "deliver",
    "demand", "demise", "demo", "denial", "denim", "dense", "deny", "depart",
    "depend", "depict", "deploy", "deposit", "depot", "depth", "deputy", "derive",
    "desert", "design", "desire", "desk", "desktop", "despair", "despite",
    "dessert", "destiny", "destroy", "detail", "detect", "develop", "device",
    "devote", "diagram", "dial", "diamond", "diary", "diesel", "diet", "differ",
    "digest", "dignity", "dilemma", "dining", "dinner", "dioxide", "diploma",
    "direct", "dirt", "disable", "disco", "discount", "discover", "disease",
    "dismiss", "display", "dispute", "distant", "distinct", "district", "divide",
    "divine", "dizzy", "doctor", "document", "dollar", "domain", "donate",
    "donkey", "donor", "doom", "door", "dose", "double", "doubt", "dough",
    "downtown", "dozen", "draft", "dragon", "drain", "drama", "drastic", "drawer",
    "dream", "dress", "dried", "drift", "drill", "drink", "drive", "driver",
    "drop", "drought", "drove", "drown", "drug", "drum", "drunk", "dry", "dual",
    "dubious", "duck", "dude", "due", "duke", "dull", "dumb", "dump", "during",
    "dust", "duty", "dwarf", "dwell", "dying", "dynamic", "eager", "eagle",
    "early", "earn", "earth", "ease", "east", "eastern", "easy", "echo", "eclipse",
    "ecology", "economy", "ecstasy", "edge", "edit", "editor", "educate", "effect",
    "effort", "eight", "either", "elbow", "elder", "elect", "elegant", "element",
    "elephant", "elite", "else", "embrace", "emerge", "emotion", "emperor",
    "empire", "employ", "empty", "enable", "enamel", "endure", "enemy", "energy",
    "enforce", "engage", "engine", "enjoy", "enlarge", "enlist", "enough",
    "enrich", "enroll", "ensure", "enter", "entire", "entity", "entrance",
    "envelop", "envy", "epic", "episode", "equal", "equip", "equity", "erase",
    "erect", "erode", "error", "erupt", "escape", "essay", "estate", "esteem",
    "ethnic", "evade", "evaluate", "even", "event", "evident", "evil", "evolve",
    "exact", "excel", "excess", "excuse", "execute", "exempt", "exercise",
    "exhaust", "exhibit", "exile", "exist", "exit", "expand", "expect", "expire",
    "explain", "exploit", "explore", "export", "expose", "extend", "extra",
    "extreme", "fabric", "facial", "facile", "factor", "factory", "faculty",
    "fade", "fail", "faint", "fair", "faith", "fake", "false", "fame", "familiar",
    "family", "famine", "famous", "fan", "fancy", "fantasy", "far", "fare",
    "farm", "fashion", "fast", "fasten", "fatal", "fate", "father", "fault",
    "favor", "feast", "feat", "feature", "federal", "fee", "feed", "feedback",
    "feel", "fellow", "female", "fence", "ferry", "fertile", "fetch", "fever",
    "few", "fiber", "fiction", "field", "fierce", "fifteen", "fight", "figure",
    "file", "fill", "film", "filter", "final", "finance", "find", "fine", "finger",
    "finish", "fire", "firm", "first", "fiscal", "fish", "fit", "fitness", "five",
    "fix", "flag", "flake", "flame", "flank", "flash", "flat", "flavor", "flee",
    "fleet", "flesh", "flex", "flight", "flip", "float", "flock", "flood", "floor",
    "flour", "flow", "flower", "fluid", "flurry", "flush", "flyer", "foam",
    "focus", "fog", "fold", "folder", "follow", "fond", "food", "fool", "force",
    "forecast",     "forest", "forever", "forge", "fork", "form", "formal", "format", "former",
    "formula", "forth", "fortune", "forum", "forward", "fossil", "foster",
    "found", "fountain", "four", "fox", "fraction", "frame", "frank", "fraud",
    "free", "freedom", "freeze", "freight", "fresh", "friend", "frog", "front",
    "frost", "frozen", "fruit", "frustrate", "fuel", "fulfill", "full", "fun",
    "function", "fund", "funeral", "funny", "fur", "furnace", "furnish", "furrow",
    "future", "gain", "galaxy", "gallery", "gallon", "gambit", "game", "gamma",
    "gang", "gap", "garage", "garden", "garlic", "garment", "gas", "gate",
    "gather", "gauge", "gaze", "gear", "gender", "gene", "general", "genesis",
    "genetic", "genius", "genre", "gentle", "genuine", "gesture", "get", "ghost",
    "giant", "gift", "gig", "glimpse", "global", "globe", "glory", "gloss",
    "glove", "glow", "glue", "goal", "gold", "golf", "good", "gorge", "gorilla",
    "gospel", "gossip", "govern", "gown", "grab", "grace", "grade", "grain",
    "grand", "grant", "grape", "graph", "grasp", "grass", "grate", "grave",
    "gravy", "gray", "grease", "great", "greed", "green", "greet", "grief",
    "grill", "grin", "grind", "grip", "grocery", "groove", "gross", "ground",
    "group", "grow", "growth", "guarantee", "guard", "guess", "guest", "guide",
    "guild", "guilt", "guitar", "gulf", "gun", "guru", "gut", "gym", "habit",
    "habitat", "hail", "hair", "half", "hall", "halt", "ham", "hammer", "hand",
    "handle", "handy", "hang", "happen", "happy", "harbor", "hard", "hardware",
    "harm", "harmony", "harness", "harvest", "hash", "haste", "hat", "hatch",
    "hate", "haunt", "haven", "havoc", "hawk", "hazard", "head", "heal", "health",
    "heap", "hear", "heart", "heat", "heaven", "heavy", "hedge", "heel", "height",
    "heir", "helix", "hell", "hello", "helmet", "help", "hem", "hemp", "hence",
    "herb", "herd", "here", "heritage", "hero", "heroic", "heroin", "hide",
    "hierarchy", "high", "highlight", "highway", "hike", "hill", "hint", "hip",
    "hire", "history", "hit", "hobby", "hog", "hold", "hole", "holiday", "hollow",
    "home", "honest", "honey", "honor", "hood", "hook", "hope", "horizon",
    "horn", "horror", "horse", "hospital", "host", "hot", "hotel", "hour",
    "house", "housing", "hover", "howl", "hub", "hug", "huge", "human", "humble",
    "humor", "hunger", "hunt", "hurdle", "hurry", "hurt", "husband", "hut",
    "hybrid", "icon", "idea", "ideal", "idiom", "idle", "idol", "ignite", "ignore",
    "ill", "image", "imagine", "impact", "import", "impose", "improve", "impulse",
    "income", "increase", "indeed", "index", "indoor", "induce", "infant",
    "inform", "inject", "injure", "inline", "inn", "inner", "input", "inquest",
    "inquiry", "insect", "insert", "inside", "insist", "insomnia", "inspect",
    "install", "instant", "instead", "insulin", "insult", "insure", "intact",
    "intake", "intend", "intense", "intent", "interest", "interface", "interim",
    "internal", "internet", "interval", "intimate", "into", "intrigue", "invade",
    "invent", "invest", "invite", "invoke", "involve", "iodine", "iron", "irony",
    "island", "isolate", "issue", "item", "itself", "ivory", "jack", "jacket",
    "jail", "jam", "jar", "jazz", "jean", "jeep", "jelly", "jewel", "job",
    "jockey", "join", "joint", "joke", "journal", "journey", "joy", "judge",
    "juice", "july", "jump", "june", "jungle", "junior", "junk", "jury", "just",
    "justice", "kangaroo", "keen", "keep", "kennel", "kernel", "ketchup", "key",
    "keyboard", "kick", "kid", "kidney", "kill", "kind", "king", "kingdom",
    "kiss", "kit", "kitchen", "kite", "kitten", "knee", "knife", "knight",
    "knit", "knob", "knock", "knot", "know", "knowledge", "label", "labor",
    "lace", "lack", "ladder", "lady", "lagoon", "lake", "lamb", "lamp", "land",
    "landscape", "lane", "language", "lap", "large", "laser", "last", "late",
    "later", "latin", "latter", "laugh", "launch", "laundry", "lava", "law",
    "lawn", "lawsuit", "lawyer", "lay", "layer", "layout", "lazy", "lead",
    "leader", "leaf", "league", "leak", "lean", "leap", "learn", "lease",
    "leather", "leave", "lecture", "ledge", "left", "legal", "legend", "lemon",
    "lend", "length", "lens", "less", "lesson", "test", "let", "letter", "level",
    "lever", "liable", "liar", "liberal", "liberty", "library", "license", "lid",
    "lie", "life", "lift", "light", "like", "likely", "limb", "lime", "limit",
    "limp", "line", "linear", "linen", "liner", "link", "lion", "lip", "liquid",
    "list", "listen", "literally", "literary", "litter", "little", "live",
    "lively", "liver", "living", "load", "loaf", "loan", "lobby", "local",
    "locate", "lock", "lodge", "log", "logic", "login", "logo", "lonely",
    "long", "look", "loop", "loose", "lord", "lorem", "lose", "loss", "lost",
    "lot", "loud", "love", "lovely", "lover", "low", "lower", "loyal", "luck",
    "lucky", "luggage", "lumber", "lump", "lunch", "lung", "luxury", "lyric",
    "machine", "mad", "magazine", "magic", "magnet", "magnify", "maid", "mail",
    "main", "mainly", "maintain", "major", "make", "maker", "male", "mall",
    "malt", "man", "manage", "manner", "mansion", "manual", "map", "marble",
    "march", "margin", "marine", "mark", "market", "marriage", "mask", "mass",
    "massive", "master", "match", "mate", "material", "matter", "mature",
    "maximum", "maybe", "mayor", "maze", "meadow", "meal", "mean", "means",
    "measure", "meat", "mechanic", "medal", "media", "medical", "medium", "meet",
    "meeting", "melody", "melt", "member", "memory", "mental", "mention", "menu",
    "merchant", "mercy", "merge", "merit", "merry", "mesh", "mess", "message",
    "metal", "method", "mid", "middle", "might", "mile", "milk", "mill", "mind",
    "mine", "mineral", "minimal", "minimum", "mining", "minor", "minute",
    "miracle", "mirror", "miss", "missile", "mission", "mist", "mistake", "mix",
    "mixture", "mobile", "mode", "model", "modern", "modest", "module", "moist",
    "mold", "moment", "money", "monitor", "monkey", "month", "mood", "moon",
    "moral", "more", "morning", "mortal", "mortgage", "mosaic", "most", "mostly",
    "mother", "motion", "motor", "motto", "mount", "mountain", "mouse", "mouth",
    "move", "movie", "much", "mud", "mug", "multiply", "mural", "muscle", "museum",
    "music", "mutual", "mystery", "myth", "nail", "naked", "name", "narrow",
    "nation", "native", "natural", "nature", "navy", "near", "neat", "neck",
    "need", "needle", "neglect", "neighbor", "neither", "nephew", "nerve",
    "nest", "net", "network", "neutral", "never", "new", "news", "next",
    "nice", "night", "nine", "noble", "nobody", "node", "noise", "none", "noon",
    "nor", "normal", "north", "nose", "not", "note", "nothing", "notice",
    "notify", "notion", "novel", "now", "number", "nurse", "nut", "nylon",
    "oak", "object", "observe", "obtain", "obvious", "occur", "ocean", "odd",
    "odds", "off", "offense", "offer", "office", "officer", "often", "oil",
    "okay", "old", "olive", "omit", "once", "one", "onion", "online", "only",
    "open", "opera", "opinion", "option", "oracle", "orange", "orbit", "orchard",
    "order", "organ", "origin", "other", "out", "outdoor", "outer", "output",
    "outside", "oval", "oven", "over", "overall", "overcome", "overlap", "overt",
    "owe", "own", "owner", "oxygen", "ozone", "pace", "pack", "package", "pad",
    "page", "paid", "pain", "paint", "pair", "palace", "pale", "palm", "pan",
    "panel", "panic", "pant", "paper", "parade", "parcel", "parent", "parish",
    "park", "parlor", "part", "partial", "partner", "party", "pass", "passage",
    "passion", "passive", "password", "past", "paste", "pastor", "patch", "path",
    "patience", "patient", "patrol", "patron", "pattern", "pause", "pave",
    "paw", "pay", "payment", "peace", "peak", "pearl", "peasant", "pebble",
    "peel", "peer", "pen", "penalty", "pencil", "penny", "people", "pepper",
    "per", "perceive", "perfect", "perform", "perfume", "perhaps", "period",
    "permit", "person", "pet", "petrol", "phantom", "phase", "phenomenon",
    "philosophy", "phone", "photo", "phrase", "physic", "piano", "pick", "picture",
    "pie", "piece", "pier", "pigeon", "pile", "pill", "pillar", "pilot", "pin",
    "pine", "pink", "pint", "pipe", "pit", "pitch", "pizza", "place", "plain",
    "plan", "plane", "planet", "plant", "plastic", "plate", "platform", "play",
    "player", "please", "pledge", "plot", "pluck", "plug", "plum", "plumber",
    "plunge", "plus", "pocket", "poem", "poet", "poetry", "point", "polar",
    "pole", "police", "policy", "polish", "polite", "pollen", "pond", "pool",
    "poor", "pop", "popular", "porch", "pork", "port", "porter", "portion",
    "pose", "position", "positive", "possess", "possible", "post", "poster",
    "pot", "potato", "potent", "potion", "pottery", "pound", "pour", "poverty",
    "powder", "power", "practice", "praise", "pray", "preach", "precede",
    "precise", "predict", "prefer", "prelude", "premise", "premium", "prepare",
    "presence", "present", "preserve", "press", "pressure", "prestige", "prevent",
    "previous", "price", "pride", "priest", "prime", "prince", "princess",
    "principal", "print", "prior", "prism", "prison", "privacy", "private",
    "privilege", "prize", "pro", "probe", "problem", "proceed", "process",
    "produce", "product", "profit", "program", "project", "promise", "promote",
    "prompt", "proof", "propel", "proper", "property", "prophet", "proposal",
    "propose", "prospect", "protect", "protein", "protest", "proud", "prove",
    "provide", "provoke", "proximity", "prune", "psalm", "public", "publish",
    "pull", "pulse", "pump", "punch", "punctual", "punish", "punk", "pupil",
    "puppet", "purchase", "pure", "purple", "purpose", "purse", "pursue",
    "push", "put", "puzzle", "pyramid", "qualify", "quality", "quantity",
    "quarrel", "quarter", "queen", "query", "quest", "question", "queue",
    "quick", "quiet", "quit", "quite", "quote", "rabbit", "race", "rack",
    "radar", "radical", "radio", "radius", "rage", "raid", "rail", "rain",
    "raise", "rally", "ram", "ramp", "ranch", "rand", "random", "range", "rank",
    "rapid", "rare", "rash", "rat", "rate", "rather", "ratio", "raw", "reach",
    "react", "read", "reader", "ready", "real", "reality", "realize", "realm",
    "reap", "rear", "reason", "recall", "receipt", "receive", "recent", "recipe",
    "reckon", "record", "recover", "red", "redeem", "reduce", "refer", "reflect",
    "reform", "refuge", "refuse", "regard", "regime", "region", "register",
    "regret", "regular", "reign", "reject", "relate", "relax", "release",
    "relent", "reliant", "relief", "religion", "relish", "reluctant", "remain",
    "remark", "remedy", "remember", "remind", "remote", "remove", "render",
    "rent", "repair", "repeat", "replace", "report", "request", "require",
    "rescue", "research", "reserve", "reside", "resign", "resist", "resolve",
    "resort", "resource", "respect", "respond", "rest", "restore", "result",
    "resume", "retail", "retain", "retire", "retreat", "return", "reveal",
    "revenue", "reverse", "review", "revise", "revive", "revolt", "reward",
    "rhythm", "rib", "ribbon", "rice", "rich", "ride", "ridge", "rifle",
    "right", "rigid", "rim", "ring", "riot", "rip", "ripe", "rise", "risk",
    "ritual", "rival", "river", "road", "roam", "roar", "roast", "rob", "robe",
    "rock", "rocket", "rod", "role", "roll", "romance", "roof", "room", "root",
    "rope", "rose", "rotate", "rough", "round", "route", "routine", "row",
    "royal", "rub", "rubber", "rude", "rug", "ruin", "rule", "ruler", "rumor",
    "run", "rural", "rush", "rust", "sack", "sacred", "sad", "saddle", "safe",
    "safety", "sage", "sail", "saint", "salad", "salary", "sale", "salmon",
    "salt", "salute", "same", "sample", "sand", "sandwich", "satellite", "satin",
    "satisfy", "sauce", "save", "saving", "scale", "scan", "scandal", "scarce",
    "scare", "scarf", "scene", "scent", "schedule", "scheme", "scholar", "school",
    "science", "scissors", "scope", "score", "scout", "scramble", "scream",
    "screen", "script", "scroll", "scrub", "seal", "search", "season", "seat",
    "second", "secret", "section", "sector", "secure", "seed", "seek", "segment",
    "select", "self", "sell", "senate", "senior", "sense", "sensitive", "sensor",
    "sent", "sentence", "separate", "sequence", "serial", "series", "serious",
    "serve", "service", "session", "set", "settle", "setup", "seven", "severe",
    "shade", "shadow", "shaft", "shake", "shall", "shallow", "shame", "shape",
    "share", "shark", "sharp", "shed", "sheep", "sheer", "sheet", "shelf",
    "shell", "shelter", "shield", "shift", "shine", "ship", "shirt", "shock",
    "shoe", "shoot", "shop", "shore", "short", "shot", "should", "shout",
    "shove", "show", "shower", "shrimp", "shrink", "shrug", "shut", "sick",
    "side", "siege", "sigh", "sight", "sign", "signal", "silence", "silicon",
    "silk", "silly", "silver", "similar", "simple", "since", "sing", "single",
    "sink", "sip", "sister", "sit", "site", "situation", "six", "size", "sketch",
    "ski", "skill", "skin", "skip", "skirt", "skull", "sky", "slab", "slack",
    "slap", "slave", "sleep", "slice", "slide", "slight", "slip", "slope",
    "slow", "small", "smart", "smell", "smile", "smoke", "smooth", "snack",
    "snake", "snap", "snow", "soak", "soap", "soar", "social", "sock", "soda",
    "sofa", "soft", "software", "soil", "solar", "sold", "soldier", "sole",
    "solid", "solution", "solve", "some", "son", "song", "soon", "sophisticated",
    "sore", "sorry", "sort", "soul", "sound", "soup", "source", "south", "space",
    "spare", "spark", "speak", "special", "species", "specific", "speech",
    "speed", "spell", "spend", "spice", "spider", "spin", "spine", "spirit",
    "split", "spoken", "sponsor", "spoon", "sport", "spot", "spray", "spread",
    "spring", "spy", "square", "stable", "stack", "staff", "stage", "stair",
    "stake", "stall", "stamp", "stand", "standard", "star", "stare", "start",
    "state", "status", "stay", "steady", "steal", "steam", "steel", "steep",
    "steer", "stem", "step", "stick", "stiff", "still", "stock", "stomach",
    "stone", "stool", "stop", "storage", "store", "storm", "story", "stove",
    "strange", "stranger", "strap", "strategy", "stream", "street", "strength",
    "stress", "stretch", "strict", "strike", "string", "strip", "stroke",
    "strong", "structure", "struggle", "student", "studio", "study", "stuff",
    "style", "subject", "submit", "substance", "succeed", "success", "such",
    "suck", "sudden", "suffer", "sugar", "suggest", "suit", "sum", "summer",
    "summit", "sun", "super", "superb", "supply", "support", "suppose", "sure",
    "surface", "surge", "surgeon", "surplus", "surprise", "surround", "survey",
    "survive", "suspect", "suspend", "sustain", "swallow", "swamp", "swap",
    "swear", "sweat", "sweep", "sweet", "swell", "swift", "swim", "swing",
    "switch", "sword", "symbol", "syrup", "system", "table", "tablet", "tackle",
    "tact", "tactic", "tag", "tail", "tailor", "take", "tale", "talent", "talk",
    "tall", "tank", "tap", "tape", "target", "task", "taste", "tax", "teach",
    "teacher", "team", "tear", "tease", "tech", "technique", "technology",
    "temple", "tenant", "tend", "tender", "tennis", "tense", "tension", "tent",
    "term", "terminal", "terrain", "terrible", "territory", "terror", "test",
    "text", "texture", "thank", "theme", "theory", "therapy", "there", "thermal",
    "thick", "thief", "thin", "thing", "think", "third", "thirst", "thirteen",
    "thirty", "thorn", "thought", "thousand", "thread", "threat", "three",
    "thrill", "throat", "throne", "through", "throw", "thumb", "thunder",
    "ticket", "tide", "tidy", "tie", "tiger", "tight", "tile", "till", "time",
    "timely", "timing", "tin", "tiny", "tip", "tire", "tired", "tissue", "title",
    "toast", "tobacco", "today", "toe", "toilet", "token", "tolerance", "tomato",
    "tone", "tongue", "tonight", "tool", "tooth", "top", "topic", "torch",
    "tornado", "torque", "torso", "total", "touch", "tough", "tour", "tourist",
    "toward", "towel", "tower", "town", "toxic", "trace", "track", "tract",
    "trade", "tradition", "traffic", "tragedy", "trail", "train", "trait",
    "transaction", "transfer", "transform", "transit", "transmit", "transport",
    "trap", "trash", "travel", "tray", "treasure", "treat", "treaty", "tree",
    "trek", "tremendous", "trend", "trial",     "tribe", "trick", "trigger", "trill",
    "trim", "trio", "trip", "triumph", "troop", "trophy", "tropical", "trouble",
    "truck", "true", "truly", "trunk", "trust", "truth", "try", "tube", "tuck",
    "tulip", "tumble", "tune", "tunnel", "turbo", "turkey", "turn", "turner",
    "turtle", "tutor", "tuxedo", "tweet", "twelve", "twenty", "twice", "twin",
    "twist", "two", "type", "typical", "ugly", "umbrella", "unable", "uncle",
    "under", "unfair", "unfold", "uniform", "union", "unique", "unit", "unite",
    "unity", "universal", "universe", "unknown", "unless", "unlike", "unlock",
    "unusual", "update", "upgrade", "uphold", "upon", "upper", "upset", "urban",
    "urge", "urgent", "usage", "use", "used", "useful", "useless", "user",
    "usual", "utility", "vacant", "vacation", "vacuum", "valid", "valley",
    "value", "valve", "van", "vanish", "vapor", "variable", "variety", "various",
    "vast", "vault", "vector", "vegetable", "vehicle", "veil", "vein", "velvet",
    "vendor", "venture", "venue", "verb", "verify", "verse", "version", "versus",
    "vertical", "vessel", "veteran", "viable", "vibrant", "vice", "victim",
    "victory", "video", "view", "vigor", "villa", "village", "vintage", "violin",
    "virtual", "virtue", "virus", "visa", "visit", "visual", "vital", "vivid",
    "vocal", "voice", "void", "volcano", "volume", "voluntary", "vote", "vow",
    "voyage", "wage", "wagon", "waist", "wait", "wake", "walk", "wall", "wallet",
    "wander", "want", "war", "warm", "warn", "wash", "waste", "watch", "water",
    "wave", "wax", "way", "weak", "wealth", "weapon", "wear", "weather", "weave",
    "web", "wedding", "weed", "week", "weekend", "weight", "weird", "welcome",
    "welfare", "well", "west", "western", "wet", "whale", "wheat", "wheel",
    "where", "which", "while", "whip", "whisper", "white", "whole", "why",
    "wicked", "wide", "width", "wife", "wild", "will", "win", "wind", "window",
    "wine", "wing", "winner", "winter", "wire", "wisdom", "wise", "wish", "wit",
    "witch", "witness", "wolf", "woman", "wonder", "wood", "wool", "word",
    "work", "worker", "world", "worm", "worry", "worship", "worth", "wound",
    "wrap", "wreck", "wrist", "write", "writer", "wrong", "yard", "year",
    "yellow", "yes", "yesterday", "yet", "yield", "young", "youth", "zone",
}

# ---------------------------------------------------------------------------
# Try to load wordfreq for larger, frequency-ranked word list
# ---------------------------------------------------------------------------
_HAS_WORDFREQ = False
_WORDFREQ_WORDS: list[str] = []

try:
    import wordfreq as _wf
    _WORDFREQ_WORDS = _wf.top_n_list('en', 10000, wordlist='best')
    _HAS_WORDFREQ = True
    logger.info("wordfreq loaded – %d English words available", len(_WORDFREQ_WORDS))
except ImportError:
    logger.info("wordfreq not available – using built-in word list (%d words)", len(_FALLBACK_WORDS))

# ---------------------------------------------------------------------------
# Build the effective word set
# ---------------------------------------------------------------------------
def _get_word_set() -> set[str]:
    if _HAS_WORDFREQ:
        return set(_WORDFREQ_WORDS) | _FALLBACK_WORDS
    return _FALLBACK_WORDS

ENGLISH_WORDS = _get_word_set()

# ---------------------------------------------------------------------------
# Common startup / brand suffixes (Domain Investor Mode)
# ---------------------------------------------------------------------------
STARTUP_SUFFIXES = {"ify", "ly", "io", "hub", "lab", "ix", "oz", "um", "us", "is", "os", "ex", "ox", "ix"}
STARTUP_PREFIXES = {"vel", "nex", "zent", "lux", "ady", "nov", "rev", "ev", "opt", "apt", "ver"}

VOWELS = set("aeiou")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

# ---------------------------------------------------------------------------
# High-value industry keywords for commercial intent scoring
# ---------------------------------------------------------------------------
INDUSTRY_KEYWORDS: dict[str, int] = {
    # Finance & Payments
    "pay": 10, "payment": 10, "cash": 9, "fund": 9, "bank": 9, "credit": 9,
    "finance": 9, "financial": 9, "invest": 9, "wealth": 9, "capital": 9,
    "trade": 8, "stock": 8, "market": 8, "coin": 8, "crypto": 8, "token": 8,
    "wallet": 9, "loan": 9, "mortgage": 9, "insure": 9, "insurance": 9,
    "money": 8, "dollar": 8, "account": 8, "fintech": 10,
    # Technology & AI
    "data": 9, "cloud": 9, "smart": 9, "tech": 8, "digital": 8, "software": 8,
    "app": 8, "web": 7, "cyber": 8, "compute": 8, "algorithm": 8, "neural": 9,
    "vision": 8, "voice": 8, "robot": 8, "drone": 7, "autonomous": 8,
    "analytics": 8, "insight": 7, "predict": 7, "deep": 7, "learn": 8,
    "intelligence": 9, "cognitive": 8, "ai": 10, "ml": 8, "gpt": 9,
    # SaaS & Business
    "saas": 9, "platform": 8, "suite": 7, "flow": 7, "sync": 7, "link": 7,
    "hub": 7, "manage": 7, "dashboard": 7, "metric": 6, "crm": 7, "erp": 7,
    "billing": 7, "invoice": 7, "subscription": 7, "workflow": 7, "collab": 7,
    "team": 6, "project": 6, "track": 6, "report": 6,
    # Healthcare
    "health": 9, "care": 8, "med": 8, "medical": 8, "doctor": 7, "clinic": 7,
    "pharma": 8, "wellness": 7, "fitness": 7, "therapy": 7, "dental": 7,
    "surgery": 7, "vision": 7, "heart": 7, "life": 6, "cure": 7,
    # Real Estate
    "estate": 9, "realestate": 9, "property": 8, "rental": 7, "apartment": 7,
    "condo": 7, "realtor": 8, "home": 7, "house": 7, "land": 6, "roof": 6,
    "solar": 8, "energy": 8, "power": 7,
    # Travel & Hospitality
    "travel": 9, "tour": 7, "trip": 7, "flight": 8, "hotel": 8, "resort": 7,
    "vacation": 7, "booking": 8, "rental": 7, "cruise": 7, "voyage": 7,
    "adventure": 6, "explore": 6,
    # E-commerce
    "shop": 8, "buy": 7, "store": 7, "deal": 7, "price": 7, "sell": 7,
    "sale": 7, "order": 6, "delivery": 7, "retail": 7, "wholesale": 7,
    "mart": 6, "goods": 6, "ecom": 8, "ecommerce": 9,
    # Legal & Professional
    "legal": 8, "law": 7, "attorney": 8, "lawyer": 7, "consult": 7,
    "consulting": 7, "solutions": 6, "services": 6, "group": 5,
}

# Low-quality keywords (penalty in dictionary score)
LOW_QUALITY_KEYWORDS = {"my", "the", "best", "online", "24", "365", "world", "solutions", "services"}

# ---------------------------------------------------------------------------
# Word segmentation – split domain name into recognized English words
# ---------------------------------------------------------------------------

def _segment_name(name: str, word_set: set[str]) -> list[str]:
    """Greedy longest-match word segmentation with memoization."""
    memo: dict[str, list[str] | None] = {}

    def _segment(s: str) -> list[str] | None:
        if s in memo:
            return memo[s]
        if not s:
            return []
        # Try longest prefix first
        for end in range(len(s), 0, -1):
            prefix = s[:end]
            if prefix in word_set:
                rest = _segment(s[end:])
                if rest is not None:
                    result = [prefix] + rest
                    memo[s] = result
                    return result
        memo[s] = None
        return None

    result = _segment(name)
    return result or []

# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _word_coverage(name: str, words: list[str]) -> float:
    """What fraction of the domain characters are covered by recognized words?"""
    if not name or not words:
        return 0.0
    covered = sum(len(w) for w in words)
    return covered / len(name)


def _compute_pronounceability(name: str) -> int:
    """Score 0-100: how easy is this to pronounce for an English speaker?"""
    score = 50  # neutral start

    # Check for unusual bigrams
    unusual_bigrams = {
        "xq", "zq", "qj", "qx", "qz", "qy", "jq", "vq",
        "xz", "zx", "zw", "zv", "zt", "zs", "zr", "zm", "zn",
        "xw", "xv", "xt", "xs", "xr", "xm", "xn",
        "cq", "cg", "cj", "cv", "cz",
        "kk", "ww", "vv",
    }
    for i in range(len(name) - 1):
        bigram = name[i:i+2]
        if bigram in unusual_bigrams:
            score -= 15
        # Check for rare consonant clusters
        if i < len(name) - 2:
            cluster = name[i:i+3]
            if all(c in CONSONANTS for c in cluster):
                # 3+ consecutive consonants = hard to pronounce
                if cluster not in {"str", "str", "spr", "spl", "scr", "squ", "thr", "chr", "phr", "shr", "sch"}:
                    score -= 10

    # Check for rare starting letters
    rare_starts = {"x", "z", "q"}
    if name and name[0] in rare_starts:
        score -= 10
        # If followed by another consonant, even worse
        if len(name) > 1 and name[1] in CONSONANTS:
            score -= 10

    # Vowel ratio check
    if name:
        vr = sum(1 for c in name if c in VOWELS) / len(name)
        if 0.35 <= vr <= 0.55:
            score += 15  # ideal
        elif 0.25 <= vr < 0.35:
            score += 5
        elif vr > 0.55:
            score += 5  # vowel-heavy is still OK
        else:
            score -= 20  # consonant-heavy

    # Bonus for ending in vowel (common in brandable names)
    if name and name[-1] in VOWELS:
        score += 10

    # Bonus for CVCV pattern
    if len(name) >= 4:
        cvcv = all(
            (name[i] in CONSONANTS and name[i+1] in VOWELS)
            for i in range(0, len(name) - 1, 2)
        )
        if cvcv:
            score += 15

    # Penalty for doubled rare letters
    if re.search(r"(.)\1", name):
        # Double letters are OK for common ones like ll, ss, tt
        common_doubles = {"ll", "ss", "tt", "pp", "rr", "nn", "mm", "cc", "dd", "ff", "gg"}
        for match in re.findall(r"(.)\1", name):
            if match * 2 not in common_doubles:
                score -= 5

    return max(0, min(100, score))


def _compute_memorability(name: str, words: list[str], word_set: set[str]) -> int:
    """Score 0-100: how memorable / catchy is this domain?"""
    score = 50

    # Real English words boost memorability
    if words:
        # Bonus proportional to how much is covered by known words
        coverage = _word_coverage(name, words)
        score += int(coverage * 30)
    else:
        score -= 20

    # Short names are more memorable
    if len(name) <= 6:
        score += 15
    elif len(name) <= 8:
        score += 10
    elif len(name) <= 10:
        score += 5
    else:
        score -= 10

    # CVCV pattern (like Velora) is very memorable
    if len(name) >= 4:
        cvcv = all(
            (name[i] in CONSONANTS and name[i+1] in VOWELS)
            for i in range(0, len(name) - 1, 2)
        )
        if cvcv:
            score += 15

    # Names ending in vowel are memorable
    if name and name[-1] in VOWELS:
        score += 8

    # Common suffixes for memorability
    if any(name.endswith(suf) for suf in STARTUP_SUFFIXES):
        score += 8

    # Penalty for numbers
    if re.search(r"\d", name):
        score -= 25

    # Penalty for hyphens
    if "-" in name:
        score -= 20

    # Alliteration or rhyme boost
    if len(name) >= 3 and len(set(name)) < len(name) * 0.6:
        # Some repeated letters can be catchy (e.g. "Boba", "Coco")
        if not any(name.count(c) > len(name) * 0.5 for c in name):
            score += 8

    # Wordfreq frequency boost for common words
    if _HAS_WORDFREQ and words:
        try:
            for w in words:
                freq = _wf.zipf_frequency(w, 'en')
                if freq >= 5.0:  # very common word
                    score += 5
                elif freq >= 4.0:  # common
                    score += 3
        except Exception:
            pass

    return max(0, min(100, score))


def _compute_commercial_intent(words: list[str], name: str) -> int:
    """Score 0-100: does this domain relate to high-value commercial sectors?"""
    score = 0
    found = set()

    # Check each word against industry keywords
    for w in words:
        for kw, points in INDUSTRY_KEYWORDS.items():
            if kw in w:
                if kw not in found:
                    found.add(kw)
                    score += points

    # Also check raw name for industry keywords
    for kw, points in INDUSTRY_KEYWORDS.items():
        if kw in name and kw not in found:
            found.add(kw)
            score += points

    # Long-tail bonus: multiple commercial keywords
    if len(found) >= 2:
        score += 10
    if len(found) >= 3:
        score += 10

    return min(100, score)


def _compute_dictionary_score(name: str, words: list[str]) -> int:
    """Score 0-100: how much of this domain is real English?"""
    if not words:
        return 0
    coverage = _word_coverage(name, words)
    score = int(coverage * 80)

    # Bonus if all words are >= 3 letters (not just "a", "an", "in" etc.)
    if all(len(w) >= 3 for w in words):
        score += 10

    # Bonus for 2-word combinations (like BrightPath)
    if len(words) == 2 and all(len(w) >= 3 for w in words):
        score += 10

    # Penalty for low-quality words
    for w in words:
        if w in LOW_QUALITY_KEYWORDS:
            score -= 15

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Domain Investor Mode detection
# ---------------------------------------------------------------------------

def _is_investor_friendly(name: str) -> bool:
    """Check if a non-dictionary name sounds like a startup/investor-quality brand.

    Examples: Velora, Nexora, Lucexa, Adyvia, Zentro, Aveni, Kivara
    """
    if len(name) < 4 or len(name) > 9:
        return False

    # Must be all letters
    if not name.isalpha():
        return False

    # Common unusual bigrams that disqualify investor friendliness
    UNUSUAL_BIGRAMS = {
        "xq", "zq", "qj", "qx", "qz", "qy", "xz", "zx",
        "zw", "zv", "zt", "zs", "zr", "zm", "zn",
        "xw", "xv", "xk", "xh", "cq", "cg", "cj", "cv", "cz",
        "kk", "ww", "vv", "jz", "jq", "jx",
    }
    for i in range(len(name) - 1):
        if name[i:i+2] in UNUSUAL_BIGRAMS:
            return False

    vowels_count = sum(1 for c in name if c in VOWELS)
    consonants_count = len(name) - vowels_count

    # Need at least 2 vowels and 2 consonants for a pronounceable name
    if vowels_count < 2 or consonants_count < 2:
        return False

    # Should have reasonable vowel ratio
    vr = vowels_count / len(name)
    if vr < 0.3 or vr > 0.7:
        return False

    # Pattern 1: CVCV(C)V – alternating consonants and vowels
    alternating = True
    for i in range(len(name) - 1):
        this_is_vowel = name[i] in VOWELS
        next_is_vowel = name[i+1] in VOWELS
        if this_is_vowel == next_is_vowel:
            alternating = False
            break
    if alternating:
        return True

    # Pattern 2: Ends in a startup-friendly suffix (-ify, -ly, -io, -hub, -lab, -ix)
    if any(name.endswith(suf) for suf in STARTUP_SUFFIXES):
        # Only qualify if the root (before suffix) has at least 2 vowels and 2 consonants
        return vowels_count >= 2 and consonants_count >= 2

    # Pattern 3: Starts with a startup-friendly prefix
    if any(name.startswith(pre) for pre in STARTUP_PREFIXES):
        return True

    # Pattern 4: Ends in vowel, reasonable structure
    if name[-1] in VOWELS:
        # Check for 3+ consecutive consonants (rare in English, hard to pronounce)
        for i in range(len(name) - 2):
            if all(c in CONSONANTS for c in name[i:i+3]):
                if name[i:i+3] not in {"str", "spr", "spl", "scr", "squ", "thr", "chr", "phr", "shr", "sch"}:
                    return False
        return True

    return False


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def compute_english_score(domain: str) -> dict:
    """Compute comprehensive English word quality scores for a domain.

    Returns dict with:
      - dictionary_score: 0-100 (how much is real English)
      - pronounceability_score: 0-100
      - memorability_score: 0-100
      - commercial_intent_score: 0-100
      - combined_score: 0-100 (weighted average)
      - has_english_words: bool
      - is_investor_friendly: bool
      - segments: list of recognized word segments
      - dominant_language: "english" | "investor" | "unknown"
    """
    name = domain.replace(".com", "").lower()

    # Word segmentation
    words = _segment_name(name, ENGLISH_WORDS)

    # Individual scores
    dict_score = _compute_dictionary_score(name, words)
    pronounce_score = _compute_pronounceability(name)
    memo_score = _compute_memorability(name, words, ENGLISH_WORDS)
    comm_score = _compute_commercial_intent(words, name)
    inv_friendly = _is_investor_friendly(name)

    has_english = dict_score >= 30 and len(words) > 0

    # Combined score: weighted average
    # Dictionary and commercial get higher weight if English words found;
    # pronounceability and memorability matter regardless
    if has_english:
        combined = (
            0.30 * dict_score
            + 0.20 * pronounce_score
            + 0.15 * memo_score
            + 0.35 * comm_score
        )
    else:
        # Non-dictionary: rely on pronounceability and memorability
        if inv_friendly:
            combined = (
                0.05 * dict_score
                + 0.40 * pronounce_score
                + 0.30 * memo_score
                + 0.10 * comm_score
                + 15.0  # investor mode bonus
            )
        else:
            combined = (
                0.05 * dict_score
                + 0.40 * pronounce_score
                + 0.30 * memo_score
                + 0.10 * comm_score
            )

    # Determine dominant language
    if has_english:
        dominant = "english"
    elif inv_friendly:
        dominant = "investor"
    else:
        dominant = "unknown"

    return {
        "dictionary_score": dict_score,
        "pronounceability_score": pronounce_score,
        "memorability_score": memo_score,
        "commercial_intent_score": comm_score,
        "combined_score": round(combined, 2),
        "has_english_words": has_english,
        "is_investor_friendly": inv_friendly,
        "segments": words,
        "dominant_language": dominant,
    }


# ---------------------------------------------------------------------------
# Pre-filter for scraper – reject truly random / unpronounceable domains
# ---------------------------------------------------------------------------

def is_random_garbage(name: str) -> bool:
    """Check if a domain is truly random/unpronounceable garbage.

    Returns True if the domain should be filtered out at the scraper level.
    (Only the worst offenders – domains that have no English words AND
    are not investor-friendly AND are hard to pronounce.)
    """
    if not name or len(name) < 4:
        return True

    # Check if it's all letters
    if not re.match(r"^[a-z]+$", name):
        return True

    # Quick pronounceability check
    score = _compute_pronounceability(name)
    words = _segment_name(name, ENGLISH_WORDS)
    inv = _is_investor_friendly(name)

    # Keep if it has English words or is investor-friendly
    if words or inv:
        return False

    # Reject if very hard to pronounce AND no English words AND not investor-friendly
    if score < 25:
        return True

    # Check if rare letters (q, x, z) appear in awkward starting position AND no English words
    rare = {"q", "x", "z"}
    if any(c in rare for c in name):
        if name[0] in rare and len(name) > 1 and name[1] in CONSONANTS:
            return True

    # Check for 5+ consecutive consonants (extremely rare in English, unpronounceable)
    for i in range(len(name) - 4):
        if all(c in CONSONANTS for c in name[i:i+5]):
            return True

    return False
