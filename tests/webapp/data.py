"""In-memory datasets for the ByteTunnels demo app.

Everything an automation agent interacts with (products, search corpus, the
data-grid rows) lives here so the app stays a single, dependency-light project.
"""

# --------------------------------------------------------------------------- #
# Shop catalogue                                                              #
# --------------------------------------------------------------------------- #

CATEGORIES = ["Audio", "Wearables", "Computers", "Accessories", "Home"]

PRODUCTS = [
    {
        "slug": "aurora-headphones",
        "name": "Aurora Wireless Headphones",
        "category": "Audio",
        "price": 199.00,
        "old_price": 249.00,
        "rating": 4.8,
        "reviews": 1284,
        "badge": "Best seller",
        "emoji": "🎧",
        "tint": "#eef1f6",
        "stock": 23,
        "blurb": "Active noise cancelling over-ear headphones with 40h battery.",
        "description": (
            "Immerse yourself with adaptive active noise cancellation, plush "
            "memory-foam ear cups and a 40-hour battery. Multipoint Bluetooth "
            "lets you switch between laptop and phone instantly."
        ),
        "options": ["Midnight", "Sand", "Sage"],
    },
    {
        "slug": "pulse-earbuds",
        "name": "Pulse Pro Earbuds",
        "category": "Audio",
        "price": 129.00,
        "old_price": None,
        "rating": 4.5,
        "reviews": 642,
        "badge": None,
        "emoji": "🎵",
        "tint": "#f6eeef",
        "stock": 58,
        "blurb": "Compact ANC earbuds with wireless charging case.",
        "description": (
            "Tiny but mighty. Pulse Pro earbuds deliver punchy bass, six hours "
            "per charge and a pocketable wireless-charging case."
        ),
        "options": ["White", "Graphite"],
    },
    {
        "slug": "lumen-watch",
        "name": "Lumen Smart Watch 2",
        "category": "Wearables",
        "price": 279.00,
        "old_price": 319.00,
        "rating": 4.7,
        "reviews": 987,
        "badge": "New",
        "emoji": "⌚",
        "tint": "#eaf1f7",
        "stock": 12,
        "blurb": "AMOLED fitness watch with ECG and 7-day battery.",
        "description": (
            "Track 120+ workouts, sleep and heart health on a vivid AMOLED "
            "display. Built-in GPS and a 7-day battery keep up with you."
        ),
        "options": ["41mm", "45mm"],
    },
    {
        "slug": "fit-band",
        "name": "FitBand Active",
        "category": "Wearables",
        "price": 59.00,
        "old_price": None,
        "rating": 4.3,
        "reviews": 415,
        "badge": None,
        "emoji": "📿",
        "tint": "#e9f1ec",
        "stock": 90,
        "blurb": "Lightweight activity tracker with 14-day battery.",
        "description": (
            "A featherweight band that quietly tracks steps, sleep and stress "
            "for two whole weeks between charges."
        ),
        "options": ["Black", "Coral", "Blue"],
    },
    {
        "slug": "nimbus-laptop",
        "name": "Nimbus 14 Ultrabook",
        "category": "Computers",
        "price": 1099.00,
        "old_price": 1299.00,
        "rating": 4.9,
        "reviews": 356,
        "badge": "Editor's choice",
        "emoji": "💻",
        "tint": "#eef0f3",
        "stock": 7,
        "blurb": "1.1kg ultrabook, 14\" 3K display, 18h battery.",
        "description": (
            "A 1.1kg machined-aluminium ultrabook with a stunning 14-inch 3K "
            "display, all-day 18-hour battery and a whisper-quiet fanless design."
        ),
        "options": ["16GB / 512GB", "32GB / 1TB"],
    },
    {
        "slug": "vertex-keyboard",
        "name": "Vertex Mechanical Keyboard",
        "category": "Accessories",
        "price": 149.00,
        "old_price": None,
        "rating": 4.6,
        "reviews": 723,
        "badge": None,
        "emoji": "⌨️",
        "tint": "#f4efe6",
        "stock": 41,
        "blurb": "Hot-swappable 75% mechanical keyboard with knob.",
        "description": (
            "A satisfying 75% layout with hot-swappable switches, gasket mount "
            "and a programmable volume knob. Sounds and feels premium."
        ),
        "options": ["Tactile", "Linear", "Clicky"],
    },
    {
        "slug": "orbit-mouse",
        "name": "Orbit Wireless Mouse",
        "category": "Accessories",
        "price": 69.00,
        "old_price": 89.00,
        "rating": 4.4,
        "reviews": 512,
        "badge": "Deal",
        "emoji": "🖱️",
        "tint": "#f1eef5",
        "stock": 64,
        "blurb": "Ergonomic silent-click mouse, USB-C, multi-device.",
        "description": (
            "Glide effortlessly with a high-precision sensor, silent clicks and "
            "the ability to flow between three devices at the press of a button."
        ),
        "options": ["Graphite", "Rose"],
    },
    {
        "slug": "studio-monitor",
        "name": "Studio 27\" 4K Monitor",
        "category": "Computers",
        "price": 449.00,
        "old_price": None,
        "rating": 4.7,
        "reviews": 289,
        "badge": None,
        "emoji": "🖥️",
        "tint": "#e8eef0",
        "stock": 18,
        "blurb": "27\" 4K IPS display with USB-C 90W charging.",
        "description": (
            "A colour-accurate 27-inch 4K IPS panel that charges your laptop "
            "over a single USB-C cable. 99% sRGB out of the box."
        ),
        "options": ["Standard", "With stand"],
    },
    {
        "slug": "glow-lamp",
        "name": "Glow Ambient Desk Lamp",
        "category": "Home",
        "price": 89.00,
        "old_price": None,
        "rating": 4.5,
        "reviews": 198,
        "badge": None,
        "emoji": "💡",
        "tint": "#f6efe8",
        "stock": 33,
        "blurb": "16M-colour smart lamp with circadian schedules.",
        "description": (
            "Set the mood with 16 million colours, or let circadian schedules "
            "warm up your evenings automatically. App and voice control."
        ),
        "options": ["Matte White", "Walnut"],
    },
    {
        "slug": "brew-kettle",
        "name": "Brew Smart Kettle",
        "category": "Home",
        "price": 119.00,
        "old_price": 139.00,
        "rating": 4.6,
        "reviews": 364,
        "badge": "Deal",
        "emoji": "🫖",
        "tint": "#f4ece8",
        "stock": 27,
        "blurb": "Precision pour-over kettle with app schedules.",
        "description": (
            "Hit the exact temperature for every brew, schedule a morning boil "
            "from your phone and keep-warm for an hour. Gooseneck spout."
        ),
        "options": ["Steel", "Black"],
    },
    {
        "slug": "voyage-backpack",
        "name": "Voyage Tech Backpack",
        "category": "Accessories",
        "price": 99.00,
        "old_price": None,
        "rating": 4.8,
        "reviews": 845,
        "badge": "Best seller",
        "emoji": "🎒",
        "tint": "#e9f0ee",
        "stock": 52,
        "blurb": "Water-resistant 22L backpack with 16\" laptop bay.",
        "description": (
            "A clean, water-resistant 22-litre commuter pack with a padded "
            "16-inch laptop bay, hidden pockets and a luggage pass-through."
        ),
        "options": ["Charcoal", "Olive"],
    },
    {
        "slug": "echo-speaker",
        "name": "Echo Portable Speaker",
        "category": "Audio",
        "price": 89.00,
        "old_price": 109.00,
        "rating": 4.4,
        "reviews": 476,
        "badge": None,
        "emoji": "🔊",
        "tint": "#efedf4",
        "stock": 38,
        "blurb": "Rugged IP67 speaker with 24h playtime.",
        "description": (
            "Take the party anywhere with a rugged IP67-rated speaker, 24-hour "
            "playtime and stereo pairing for a bigger sound."
        ),
        "options": ["Black", "Teal", "Red"],
    },
]

PRODUCTS_BY_SLUG = {p["slug"]: p for p in PRODUCTS}


def filter_products(category=None, query=None, sort=None):
    """Return products filtered by category/query and sorted."""
    items = list(PRODUCTS)
    if category and category != "All":
        items = [p for p in items if p["category"] == category]
    if query:
        q = query.lower().strip()
        items = [
            p for p in items
            if q in p["name"].lower()
            or q in p["category"].lower()
            or q in p["blurb"].lower()
        ]
    if sort == "price-asc":
        items.sort(key=lambda p: p["price"])
    elif sort == "price-desc":
        items.sort(key=lambda p: p["price"], reverse=True)
    elif sort == "rating":
        items.sort(key=lambda p: p["rating"], reverse=True)
    return items


# --------------------------------------------------------------------------- #
# Search engine corpus                                                         #
# --------------------------------------------------------------------------- #

SEARCH_CORPUS = [
    {
        "id": "r1",
        "title": "Autonomous browser agents: a practical overview",
        "url": "https://browserlab.example/autonomous-agents",
        "site": "browserlab.example",
        "favicon": "🤖",
        "snippet": (
            "An autonomous browser agent perceives a page, plans an action and "
            "executes clicks, typing and navigation without human steps. Here is "
            "how the perceive-plan-act loop works in practice."
        ),
        "tags": ["agents", "automation", "browser"],
    },
    {
        "id": "r2",
        "title": "How web automation testing actually works",
        "url": "https://testkit.example/web-automation-guide",
        "site": "testkit.example",
        "favicon": "🧪",
        "snippet": (
            "From locating elements by role and label to waiting for network "
            "idle, this guide walks through the building blocks of reliable web "
            "automation testing."
        ),
        "tags": ["testing", "automation"],
    },
    {
        "id": "r3",
        "title": "Designing resilient element selectors",
        "url": "https://frontend.example/resilient-selectors",
        "site": "frontend.example",
        "favicon": "🎯",
        "snippet": (
            "Prefer accessible roles and stable data-testid hooks over brittle "
            "CSS paths. Resilient selectors survive redesigns and keep your "
            "automation green."
        ),
        "tags": ["selectors", "frontend"],
    },
    {
        "id": "r4",
        "title": "The perceive-plan-act loop for LLM agents",
        "url": "https://aiweekly.example/perceive-plan-act",
        "site": "aiweekly.example",
        "favicon": "🧠",
        "snippet": (
            "Large language model agents map a screenshot or DOM into structured "
            "perception, plan the next step, then act. Closing the loop with "
            "verification is what makes them reliable."
        ),
        "tags": ["agents", "llm"],
    },
    {
        "id": "r5",
        "title": "Headless vs headed browsing for automation",
        "url": "https://browserlab.example/headless-vs-headed",
        "site": "browserlab.example",
        "favicon": "🤖",
        "snippet": (
            "Headless browsers are fast and cheap, but headed runs catch visual "
            "and rendering bugs. Most teams use both across their pipeline."
        ),
        "tags": ["browser", "automation"],
    },
    {
        "id": "r6",
        "title": "Filling forms programmatically without flakiness",
        "url": "https://testkit.example/form-filling",
        "site": "testkit.example",
        "favicon": "🧪",
        "snippet": (
            "Multi-step forms trip up naive scripts. Wait for each step to "
            "become interactive, assert the field value after typing, and only "
            "then advance the wizard."
        ),
        "tags": ["forms", "testing"],
    },
    {
        "id": "r7",
        "title": "Shopping-cart flows every e-commerce test should cover",
        "url": "https://commerce.example/cart-test-flows",
        "site": "commerce.example",
        "favicon": "🛒",
        "snippet": (
            "Add to cart, update quantity, remove an item, apply a coupon and "
            "check out. These five flows catch the majority of storefront "
            "regressions."
        ),
        "tags": ["ecommerce", "testing"],
    },
    {
        "id": "r8",
        "title": "Accessibility trees and why agents love them",
        "url": "https://a11y.example/accessibility-tree-agents",
        "site": "a11y.example",
        "favicon": "♿",
        "snippet": (
            "The accessibility tree is a compact, semantic view of a page. "
            "Agents that read it act more reliably than those scraping raw HTML."
        ),
        "tags": ["accessibility", "agents"],
    },
    {
        "id": "r9",
        "title": "Waiting strategies: from sleeps to smart waits",
        "url": "https://testkit.example/waiting-strategies",
        "site": "testkit.example",
        "favicon": "🧪",
        "snippet": (
            "Hard-coded sleeps make suites slow and flaky. Learn to wait on "
            "elements, network and application state instead of the clock."
        ),
        "tags": ["testing", "automation"],
    },
    {
        "id": "r10",
        "title": "Search ranking 101 for product teams",
        "url": "https://frontend.example/search-ranking-101",
        "site": "frontend.example",
        "favicon": "🎯",
        "snippet": (
            "Relevance, recency and popularity all shape what shows up first. A "
            "gentle introduction to building a search results page that feels "
            "fast and useful."
        ),
        "tags": ["search", "frontend"],
    },
    {
        "id": "r11",
        "title": "Session, cookies and login automation",
        "url": "https://browserlab.example/login-automation",
        "site": "browserlab.example",
        "favicon": "🤖",
        "snippet": (
            "Automating sign-in means handling credentials, sessions and the "
            "redirect that follows. Reuse a stored session to skip the form on "
            "later runs."
        ),
        "tags": ["login", "automation"],
    },
    {
        "id": "r12",
        "title": "Data tables: sorting, filtering and pagination",
        "url": "https://frontend.example/data-table-patterns",
        "site": "frontend.example",
        "favicon": "🎯",
        "snippet": (
            "A good data grid lets users sort by any column, filter by keyword "
            "and page through thousands of rows without losing their place."
        ),
        "tags": ["tables", "frontend"],
    },
]


def search_corpus(query):
    """Very small ranking: title hits first, then snippet/tag hits."""
    if not query:
        return []
    q = query.lower().strip()
    scored = []
    for doc in SEARCH_CORPUS:
        score = 0
        if q in doc["title"].lower():
            score += 5
        if q in doc["snippet"].lower():
            score += 2
        if any(q in t for t in doc["tags"]):
            score += 3
        # token overlap for multi-word queries
        for token in q.split():
            if token in doc["title"].lower():
                score += 2
            elif token in doc["snippet"].lower():
                score += 1
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [doc for _, doc in scored]


SUGGESTIONS = [
    "autonomous browser agents",
    "web automation testing",
    "resilient element selectors",
    "perceive plan act loop",
    "headless vs headed browsing",
    "form filling without flakiness",
    "shopping cart test flows",
    "accessibility tree agents",
    "waiting strategies",
    "search ranking",
    "login automation",
    "data table sorting pagination",
]


def suggest(query, limit=6):
    if not query:
        return SUGGESTIONS[:limit]
    q = query.lower().strip()
    starts = [s for s in SUGGESTIONS if s.startswith(q)]
    contains = [s for s in SUGGESTIONS if q in s and s not in starts]
    return (starts + contains)[:limit]


# --------------------------------------------------------------------------- #
# Data-grid dataset (employees / teammates)                                    #
# --------------------------------------------------------------------------- #

TEAM_ROWS = [
    {"id": 1,  "name": "Ada Lovelace",     "role": "Staff Engineer",   "team": "Platform",   "location": "London",   "status": "Active",   "joined": "2019-03-12", "salary": 182000},
    {"id": 2,  "name": "Alan Turing",      "role": "Principal",        "team": "Research",    "location": "Cambridge","status": "Active",   "joined": "2018-07-01", "salary": 205000},
    {"id": 3,  "name": "Grace Hopper",     "role": "Engineering Lead", "team": "Platform",   "location": "New York", "status": "Active",   "joined": "2017-11-23", "salary": 198000},
    {"id": 4,  "name": "Katherine Johnson","role": "Data Scientist",   "team": "Research",    "location": "Houston",  "status": "Active",   "joined": "2020-01-15", "salary": 164000},
    {"id": 5,  "name": "Linus Torvalds",   "role": "Staff Engineer",   "team": "Kernel",      "location": "Portland", "status": "On leave", "joined": "2016-05-09", "salary": 188000},
    {"id": 6,  "name": "Margaret Hamilton","role": "Engineering Lead", "team": "Flight",      "location": "Boston",   "status": "Active",   "joined": "2015-09-30", "salary": 201000},
    {"id": 7,  "name": "Dennis Ritchie",   "role": "Principal",        "team": "Languages",   "location": "Murray Hill","status": "Active", "joined": "2014-02-18", "salary": 210000},
    {"id": 8,  "name": "Barbara Liskov",   "role": "Principal",        "team": "Research",    "location": "Boston",   "status": "Active",   "joined": "2018-10-02", "salary": 207000},
    {"id": 9,  "name": "Tim Berners-Lee",  "role": "Architect",        "team": "Web",         "location": "London",   "status": "Active",   "joined": "2013-06-21", "salary": 215000},
    {"id": 10, "name": "Donald Knuth",     "role": "Principal",        "team": "Languages",   "location": "Stanford", "status": "On leave", "joined": "2012-04-11", "salary": 209000},
    {"id": 11, "name": "Radia Perlman",    "role": "Staff Engineer",   "team": "Network",     "location": "Seattle",  "status": "Active",   "joined": "2019-08-19", "salary": 179000},
    {"id": 12, "name": "Ken Thompson",     "role": "Principal",        "team": "Kernel",      "location": "Murray Hill","status": "Active", "joined": "2014-12-05", "salary": 211000},
    {"id": 13, "name": "Vint Cerf",        "role": "Architect",        "team": "Network",     "location": "Washington","status": "Active",  "joined": "2013-03-28", "salary": 214000},
    {"id": 14, "name": "Shafi Goldwasser", "role": "Data Scientist",   "team": "Research",    "location": "Berkeley", "status": "Active",   "joined": "2021-02-09", "salary": 168000},
    {"id": 15, "name": "Bjarne Stroustrup","role": "Principal",        "team": "Languages",   "location": "Austin",   "status": "Active",   "joined": "2016-07-14", "salary": 206000},
    {"id": 16, "name": "Frances Allen",    "role": "Engineering Lead", "team": "Compilers",   "location": "New York", "status": "Active",   "joined": "2015-01-26", "salary": 196000},
    {"id": 17, "name": "Hedy Lamarr",      "role": "Staff Engineer",   "team": "Network",     "location": "Los Angeles","status": "On leave","joined": "2017-09-03","salary": 181000},
    {"id": 18, "name": "Claude Shannon",   "role": "Principal",        "team": "Research",    "location": "Murray Hill","status": "Active", "joined": "2012-11-19", "salary": 213000},
    {"id": 19, "name": "John McCarthy",    "role": "Architect",        "team": "AI",          "location": "Stanford", "status": "Active",   "joined": "2013-08-08", "salary": 212000},
    {"id": 20, "name": "Marvin Minsky",    "role": "Principal",        "team": "AI",          "location": "Boston",   "status": "On leave", "joined": "2014-05-22", "salary": 208000},
    {"id": 21, "name": "Edsger Dijkstra",  "role": "Principal",        "team": "Algorithms",  "location": "Austin",   "status": "Active",   "joined": "2015-10-17", "salary": 207000},
    {"id": 22, "name": "Sophie Wilson",    "role": "Staff Engineer",   "team": "Kernel",      "location": "Cambridge","status": "Active",   "joined": "2019-12-01", "salary": 184000},
    {"id": 23, "name": "Carol Shaw",       "role": "Data Scientist",   "team": "Games",       "location": "San Jose", "status": "Active",   "joined": "2020-06-30", "salary": 162000},
    {"id": 24, "name": "Anita Borg",       "role": "Engineering Lead", "team": "Platform",   "location": "Palo Alto","status": "Active",   "joined": "2018-04-04", "salary": 199000},
]

TEAM_COLUMNS = [
    {"key": "name",     "label": "Name",     "type": "text"},
    {"key": "role",     "label": "Role",     "type": "text"},
    {"key": "team",     "label": "Team",     "type": "text"},
    {"key": "location", "label": "Location", "type": "text"},
    {"key": "status",   "label": "Status",   "type": "text"},
    {"key": "joined",   "label": "Joined",   "type": "date"},
    {"key": "salary",   "label": "Salary",   "type": "number"},
]


def query_rows(q=None, sort="name", direction="asc", page=1, page_size=8):
    rows = list(TEAM_ROWS)
    if q:
        ql = q.lower().strip()
        rows = [
            r for r in rows
            if ql in r["name"].lower()
            or ql in r["role"].lower()
            or ql in r["team"].lower()
            or ql in r["location"].lower()
            or ql in r["status"].lower()
        ]
    valid = {c["key"] for c in TEAM_COLUMNS}
    if sort not in valid:
        sort = "name"
    rows.sort(key=lambda r: r[sort], reverse=(direction == "desc"))

    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    window = rows[start:start + page_size]
    return {
        "rows": window,
        "total": total,
        "page": page,
        "pages": pages,
        "start": start,
        "page_size": page_size,
    }
