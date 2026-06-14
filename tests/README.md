# ByteTunnels — browser-automation test scenarios

A small, dependency-light **Flask** web app full of realistic flows for exercising
an autonomous browser agent: search, an e-commerce store with a session-backed
cart, a multi-step checkout, login, a task manager and a sortable data grid.

Every interactive control exposes a stable [`data-testid`](#selector-cheatsheet)
hook so selectors stay resilient across redesigns.

```
tests/
└── webapp/
    ├── app.py              # Flask routes + session state (cart / login / todos)
    ├── data.py             # mock products, search corpus, data-grid rows
    ├── requirements.txt    # just Flask
    ├── static/
    │   ├── css/styles.css  # shared design system (dark + light themes)
    │   └── js/app.js        # tiny helpers (theme toggle, toasts)
    └── templates/          # one Jinja template per page
```

## Run it

```bash
cd tests/webapp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:8000>. The server runs in debug mode and reloads on edits.

Set a different port with `PORT=8080 python app.py`.

## Scenarios

| Page                | Route                | What an agent can practice |
|---------------------|----------------------|----------------------------|
| **Hub**             | `/`                  | Navigate to any scenario from cards |
| **Search**          | `/search`            | Type a query, use live autocomplete (`/api/suggest`), submit, click a result |
| **Result**          | `/search/result/<id>`| Read an article, trigger an action button |
| **Shop**            | `/shop`              | Filter by category, sort, search, add to cart |
| **Product**         | `/product/<slug>`    | Pick an option, change quantity, add to cart |
| **Cart**            | `/cart`              | Update quantities, remove items, see totals |
| **Checkout**        | `/checkout`          | Drive a 4-step wizard (contact → shipping → payment → review) |
| **Confirmation**    | `/order/confirmed`   | Read the order number / total |
| **Login**           | `/login`             | Fill credentials, handle a validation error, reach a protected page |
| **Account**         | `/account`           | Protected — redirects to login when signed out |
| **Tasks**           | `/todos`             | Add, toggle, filter and clear tasks |
| **Data grid**       | `/data`              | Search, sort by column, paginate (all via query params) |

### Demo login

```
email:    demo@bytetunnels.test
password: password123
```

There's an **Autofill demo credentials** button on the login page, and the wrong
credentials path renders a visible error for testing the unhappy flow.

## Notes for automation

- **State is real.** The cart, login session and todo list live in the Flask
  session, so actions persist across page navigations exactly like a live site.
- **Forms POST to the server** (add to cart, cart update/remove, todo
  add/toggle/delete, checkout). The data-grid and shop filters use **GET query
  params** (`?q=&sort=&dir=&page=`), so navigation alone reproduces any state.
- **JSON API:** `GET /api/suggest?q=<query>` returns autocomplete suggestions.
- The checkout wizard advances client-side and validates required fields before
  each step; the final **Place order** button is disabled until the terms
  checkbox is ticked.

## Test harnesses

| Script | What it checks | Needs |
|--------|----------------|-------|
| `agent_llm_smoke.py`  | The LLM "brain" alone — POSTs the real system prompt + a representative observation to the `.env` endpoint and asserts a parseable action. | repo-root `.env` (no browser). |
| `flow_cache_test.py`  | The **record/replay caching layer** (`chromiumfish.flow.Flow`) end-to-end. | running browser (CDP `:9222`, launched with `--agent-*`) + this webapp (`:8000`). |

### Caching test (`flow_cache_test.py`)

Drives a flow four times and asserts both the step accounting (replayed / healed
/ recorded) **and** the real number of LLM round-trips, counted from the agent
I/O log (`--agent-log-file`, one `==== step N SENT ====` per round-trip):

1. **RECORD** — cold cache, full LLM loop → steps `recorded`, plan saved to disk.
2. **REPLAY** — warm cache → every step `replayed`, **0 LLM round-trips**.
3. **HEAL**  — one descriptor corrupted → only the drifted step is `healed` (1
   round-trip), the rest `replayed`, and the repaired plan is written back.
4. **RE-REPLAY** — after self-heal → all `replayed`, 0 round-trips again.

```bash
# browser up via __tools/launch_agent.sh, webapp on :8000, then:
python3 tests/flow_cache_test.py
# retarget another scenario:
FLOW_NAME=cachetest-login FLOW_URL=http://127.0.0.1:8000/login \
  FLOW_GOAL="Log in with demo@bytetunnels.test / password123" \
  python3 tests/flow_cache_test.py
```

The default flow uses the to-do add form (top-of-page controls). Avoid driving
clicks on **below-the-fold** elements (e.g. data-grid pagination) until the
known Actor batched-click crash is fixed — see the agent-layer notes.

### Selector cheatsheet

A few of the most useful hooks (all attributes are `data-testid`):

- Search: `search-input`, `search-submit`, `search-suggestions`, `result-link-<id>`
- Shop: `filter-<category>`, `sort-select`, `add-<slug>`, `product-link-<slug>`
- Product: `qty-plus` / `qty-minus`, `add-to-cart-submit`
- Cart: `cart-plus-<slug>`, `cart-remove-<slug>`, `checkout-btn`, `summary-total`
- Checkout: `input-name`, `input-email`, `next-1`…`next-3`, `agree-terms`, `place-order`
- Login: `login-email`, `login-password`, `login-submit`, `fill-demo`, `login-error`
- Tasks: `todo-input`, `todo-add`, `toggle-<id>`, `delete-<id>`, `filter-active`
- Data grid: `table-search-input`, `sort-<column>`, `page-<n>`, `page-next`

Built as a sandbox for testing the native AI agent layer.
