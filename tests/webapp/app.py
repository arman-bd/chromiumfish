"""ByteTunnels — a small Flask app full of browser-automation playgrounds.

Run it with:

    pip install -r requirements.txt
    python app.py

then open http://127.0.0.1:5000

Every page is a self-contained scenario an autonomous browser agent can drive:
search, an e-commerce store with a real session cart, a multi-step checkout,
login, a todo app and a sortable data grid. Interactive elements expose stable
``data-testid`` hooks so selectors stay resilient.
"""

from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, abort,
)

import data

app = Flask(__name__)
app.secret_key = "bytetunnels-demo-secret-key"

DEMO_USER = {
    "email": "demo@bytetunnels.test",
    "password": "password123",
    "name": "Demo User",
}

SCENARIOS = [
    {"slug": "search",   "icon": "🔍", "title": "Search Engine",
     "desc": "Type a query, get ranked results with live suggestions, then open a result.",
     "endpoint": "search", "tag": "Search + click"},
    {"slug": "shop",     "icon": "🛍️", "title": "Online Store",
     "desc": "Browse a product grid, filter by category, open a product and add it to the cart.",
     "endpoint": "shop", "tag": "Browse + add to cart"},
    {"slug": "cart",     "icon": "🛒", "title": "Cart & Checkout",
     "desc": "Adjust quantities then complete a multi-step checkout wizard end to end.",
     "endpoint": "cart", "tag": "Multi-step form"},
    {"slug": "login",    "icon": "🔐", "title": "Login Flow",
     "desc": "Fill credentials, handle validation errors and land on an authenticated page.",
     "endpoint": "login", "tag": "Auth + session"},
    {"slug": "todos",    "icon": "✅", "title": "Task Manager",
     "desc": "Create tasks, toggle them complete, filter the list and clear what's done.",
     "endpoint": "todos", "tag": "Create / toggle / delete"},
    {"slug": "notes",    "icon": "📝", "title": "Notes",
     "desc": "Write sticky notes, colour-tag them, search and pin the ones that matter.",
     "endpoint": "notes", "tag": "Create / search / pin"},
    {"slug": "data",     "icon": "📊", "title": "Data Grid",
     "desc": "Search, sort by any column and page through a directory of records.",
     "endpoint": "table", "tag": "Sort / filter / paginate"},
    {"slug": "verify",   "icon": "☁️", "title": "Bot Check",
     "desc": "A bot-check-style “verify you are human” interstitial — tick the box to pass.",
     "endpoint": "verify", "tag": "CAPTCHA challenge"},
]


# --------------------------------------------------------------------------- #
# Globals injected into every template                                         #
# --------------------------------------------------------------------------- #

@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return {
        "cart_count": sum(cart.values()),
        "current_user": session.get("user"),
        "scenarios": SCENARIOS,
        "path": request.path,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# Cart helpers                                                                 #
# --------------------------------------------------------------------------- #

def _cart_items():
    cart = session.get("cart", {})
    items, subtotal = [], 0.0
    for slug, qty in cart.items():
        product = data.PRODUCTS_BY_SLUG.get(slug)
        if not product:
            continue
        line = product["price"] * qty
        subtotal += line
        items.append({"product": product, "qty": qty, "line_total": line})
    return items, subtotal


# --------------------------------------------------------------------------- #
# Hub                                                                          #
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- #
# Search engine                                                                #
# --------------------------------------------------------------------------- #

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = data.search_corpus(query)
    return render_template(
        "search.html", query=query, results=results,
        searched=bool(query),
    )


@app.route("/search/result/<rid>")
def search_result(rid):
    doc = next((d for d in data.SEARCH_CORPUS if d["id"] == rid), None)
    if not doc:
        abort(404)
    related = [d for d in data.SEARCH_CORPUS if d["id"] != rid][:3]
    return render_template("result.html", doc=doc, related=related)


@app.route("/api/suggest")
def api_suggest():
    query = request.args.get("q", "")
    return jsonify({"query": query, "suggestions": data.suggest(query)})


# --------------------------------------------------------------------------- #
# Store                                                                        #
# --------------------------------------------------------------------------- #

@app.route("/shop")
def shop():
    category = request.args.get("category", "All")
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "")
    products = data.filter_products(category=category, query=query, sort=sort)
    return render_template(
        "shop.html", products=products, categories=data.CATEGORIES,
        category=category, query=query, sort=sort,
    )


@app.route("/product/<slug>")
def product(slug):
    item = data.PRODUCTS_BY_SLUG.get(slug)
    if not item:
        abort(404)
    related = [p for p in data.PRODUCTS
               if p["category"] == item["category"] and p["slug"] != slug][:3]
    return render_template("product.html", product=item, related=related)


@app.route("/cart/add", methods=["POST"])
def cart_add():
    slug = request.form.get("slug", "")
    qty = max(1, int(request.form.get("qty", 1) or 1))
    if slug not in data.PRODUCTS_BY_SLUG:
        abort(400)
    cart = session.get("cart", {})
    cart[slug] = cart.get(slug, 0) + qty
    session["cart"] = cart
    flash(f"Added {data.PRODUCTS_BY_SLUG[slug]['name']} to your cart.", "brand")
    return redirect(request.form.get("next") or url_for("shop"))


@app.route("/cart")
def cart():
    items, subtotal = _cart_items()
    shipping = 0.0 if subtotal == 0 or subtotal >= 150 else 9.0
    return render_template(
        "cart.html", items=items, subtotal=subtotal,
        shipping=shipping, total=subtotal + shipping,
    )


@app.route("/cart/update", methods=["POST"])
def cart_update():
    slug = request.form.get("slug", "")
    qty = int(request.form.get("qty", 1) or 0)
    cart = session.get("cart", {})
    if slug in cart:
        if qty <= 0:
            cart.pop(slug)
        else:
            cart[slug] = qty
        session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    slug = request.form.get("slug", "")
    cart = session.get("cart", {})
    if slug in cart:
        cart.pop(slug)
        session["cart"] = cart
        flash("Item removed from cart.", "toast")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET"])
def checkout():
    items, subtotal = _cart_items()
    if not items:
        flash("Your cart is empty — add something first.", "danger")
        return redirect(url_for("shop"))
    shipping = 0.0 if subtotal >= 150 else 9.0
    return render_template(
        "checkout.html", items=items, subtotal=subtotal,
        shipping=shipping, total=subtotal + shipping,
    )


@app.route("/checkout/place", methods=["POST"])
def checkout_place():
    items, subtotal = _cart_items()
    if not items:
        return redirect(url_for("shop"))
    shipping = 0.0 if subtotal >= 150 else 9.0
    order = {
        "name": request.form.get("full_name", "Customer"),
        "email": request.form.get("email", ""),
        "address": request.form.get("address", ""),
        "city": request.form.get("city", ""),
        "items": items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
        "order_id": "AL-" + str(abs(hash(request.form.get("email", "x"))) % 900000 + 100000),
    }
    session["last_order"] = {
        "order_id": order["order_id"],
        "name": order["name"],
        "email": order["email"],
        "total": order["total"],
        "count": sum(i["qty"] for i in items),
    }
    session["cart"] = {}
    return redirect(url_for("confirmation"))


@app.route("/order/confirmed")
def confirmation():
    order = session.get("last_order")
    if not order:
        return redirect(url_for("shop"))
    return render_template("confirmation.html", order=order)


# --------------------------------------------------------------------------- #
# Auth                                                                         #
# --------------------------------------------------------------------------- #

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if email == DEMO_USER["email"] and password == DEMO_USER["password"]:
            session["user"] = {"email": email, "name": DEMO_USER["name"]}
            flash(f"Welcome back, {DEMO_USER['name']}!", "brand")
            return redirect(request.args.get("next") or url_for("account"))
        error = "Invalid email or password. Try the demo credentials below."
    return render_template("login.html", error=error, demo=DEMO_USER)


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    flash("You have been signed out.", "toast")
    return redirect(url_for("login"))


@app.route("/account")
@login_required
def account():
    return render_template("account.html")


# --------------------------------------------------------------------------- #
# Todos                                                                        #
# --------------------------------------------------------------------------- #

DEFAULT_TODOS = [
    {"id": 1, "text": "Open the search demo and look something up", "done": True},
    {"id": 2, "text": "Add a product to the cart", "done": False},
    {"id": 3, "text": "Complete the checkout wizard", "done": False},
]


def _get_todos():
    if "todos" not in session:
        session["todos"] = list(DEFAULT_TODOS)
        session["todo_seq"] = 3
    return session["todos"]


@app.route("/todos")
def todos():
    items = _get_todos()
    flt = request.args.get("filter", "all")
    if flt == "active":
        visible = [t for t in items if not t["done"]]
    elif flt == "completed":
        visible = [t for t in items if t["done"]]
    else:
        visible = items
    remaining = sum(1 for t in items if not t["done"])
    return render_template(
        "todos.html", todos=visible, filter=flt,
        remaining=remaining, total=len(items),
    )


@app.route("/todos/add", methods=["POST"])
def todos_add():
    text = request.form.get("text", "").strip()
    if text:
        items = _get_todos()
        seq = session.get("todo_seq", len(items)) + 1
        items.append({"id": seq, "text": text, "done": False})
        session["todos"] = items
        session["todo_seq"] = seq
    return redirect(url_for("todos", filter=request.form.get("filter", "all")))


@app.route("/todos/toggle", methods=["POST"])
def todos_toggle():
    tid = int(request.form.get("id", 0))
    items = _get_todos()
    for t in items:
        if t["id"] == tid:
            t["done"] = not t["done"]
            break
    session["todos"] = items
    return redirect(url_for("todos", filter=request.form.get("filter", "all")))


@app.route("/todos/delete", methods=["POST"])
def todos_delete():
    tid = int(request.form.get("id", 0))
    items = [t for t in _get_todos() if t["id"] != tid]
    session["todos"] = items
    return redirect(url_for("todos", filter=request.form.get("filter", "all")))


@app.route("/todos/clear", methods=["POST"])
def todos_clear():
    items = [t for t in _get_todos() if not t["done"]]
    session["todos"] = items
    flash("Cleared completed tasks.", "toast")
    return redirect(url_for("todos", filter=request.form.get("filter", "all")))


# --------------------------------------------------------------------------- #
# Notes                                                                        #
# --------------------------------------------------------------------------- #

NOTE_COLORS = ["yellow", "blue", "green", "pink", "purple"]

DEFAULT_NOTES = [
    {"id": 1, "title": "Welcome to Notes",
     "body": "Jot anything down here. Pick a colour, pin the important ones and "
             "use the search box to find a note fast.",
     "color": "yellow", "pinned": True},
    {"id": 2, "title": "Shopping list",
     "body": "Oat milk\nCoffee beans\nA fresh notebook",
     "color": "blue", "pinned": False},
    {"id": 3, "title": "Agent test ideas",
     "body": "Create a note, search for it, pin it, then delete it.",
     "color": "green", "pinned": False},
]


def _get_notes():
    if "notes" not in session:
        session["notes"] = list(DEFAULT_NOTES)
        session["note_seq"] = len(DEFAULT_NOTES)
    return session["notes"]


@app.route("/notes")
def notes():
    items = _get_notes()
    q = request.args.get("q", "").strip()
    if q:
        ql = q.lower()
        visible = [n for n in items
                   if ql in n["title"].lower() or ql in n["body"].lower()]
    else:
        visible = list(items)
    # Pinned first, otherwise keep insertion order.
    visible.sort(key=lambda n: not n["pinned"])
    pinned = sum(1 for n in items if n["pinned"])
    return render_template(
        "notes.html", notes=visible, q=q, colors=NOTE_COLORS,
        total=len(items), pinned=pinned, searched=bool(q),
    )


@app.route("/notes/add", methods=["POST"])
def notes_add():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    color = request.form.get("color", "yellow")
    if color not in NOTE_COLORS:
        color = "yellow"
    if title or body:
        items = _get_notes()
        seq = session.get("note_seq", len(items)) + 1
        items.insert(0, {
            "id": seq,
            "title": title or "Untitled note",
            "body": body,
            "color": color,
            "pinned": False,
        })
        session["notes"] = items
        session["note_seq"] = seq
        flash("Note saved.", "brand")
        # Redirect to a URL that CHANGES on every successful save. After a normal
        # save the form resets and the bare /notes URL + interactive-element list
        # look unchanged, so an automated agent can't tell it worked and re-submits
        # (creating duplicates). A monotonic ``saved`` id makes the URL differ each
        # time — the same "navigated" signal that stops agents looping elsewhere —
        # and ``total`` lets a reader answer "how many notes" straight from the URL.
        return redirect(url_for("notes", saved=seq, total=len(items)))
    return redirect(url_for("notes"))


@app.route("/notes/pin", methods=["POST"])
def notes_pin():
    nid = int(request.form.get("id", 0))
    items = _get_notes()
    for n in items:
        if n["id"] == nid:
            n["pinned"] = not n["pinned"]
            break
    session["notes"] = items
    return redirect(url_for("notes", q=request.form.get("q", "")))


@app.route("/notes/delete", methods=["POST"])
def notes_delete():
    nid = int(request.form.get("id", 0))
    session["notes"] = [n for n in _get_notes() if n["id"] != nid]
    flash("Note deleted.", "toast")
    return redirect(url_for("notes", q=request.form.get("q", "")))


# --------------------------------------------------------------------------- #
# BotGate — a bot-check-style bot-check interstitial (UI only)            #
# --------------------------------------------------------------------------- #

@app.route("/verify")
def verify():
    # ``site`` is the host the interstitial pretends to protect; ``next`` is
    # where the "Continue" button points once the user clears the check.
    import secrets
    site = request.args.get("site", "notes.bytetunnels.test")
    nxt = request.args.get("next") or url_for("notes")
    ray_id = secrets.token_hex(8)
    return render_template("verify.html", site=site, next_url=nxt, ray_id=ray_id)


# --------------------------------------------------------------------------- #
# Data grid                                                                    #
# --------------------------------------------------------------------------- #

@app.route("/data")
def table():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    result = data.query_rows(q=q, sort=sort, direction=direction, page=page)
    return render_template(
        "table.html", columns=data.TEAM_COLUMNS, q=q, sort=sort,
        direction=direction, **result,
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=True, port=port)
