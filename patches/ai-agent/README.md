# ai-agent

Native, in-browser-process LLM agent layer (browser-use-style page automation
that lives in the C++ browser process instead of an external CDP/JS driver).

It drives Chrome's **Actor framework** (`chrome/browser/actor`) for actions and
**AIPageContent** (`optimization_guide::GetAIPageContent`,
`ANNOTATED_PAGE_CONTENT_MODE_ACTIONABLE_ELEMENTS`) for perception, with the
"brain" loop calling a user-configured **OpenAI-compatible** `/chat/completions`
endpoint (e.g. OpenRouter) over `network::SimpleURLLoader`. Clicks/moves go
through a chrome-side port of the fork's humanized cursor path
(`RenderWidgetHost::ForwardMouseEvent`, no `kFromDebugger`); type/scroll/select/
navigate/wait go through Actor `ToolRequest`s. It is exposed as a new async CDP
command `Browser.agentRunTask`.

## Files

`agent-layer.patch` contains the **fork-new files** (one-patch-per-file rule —
none of these are touched by any other patch):

| File | Role |
|------|------|
| `chrome/browser/ai_agent/agent_controller.{h,cc}` | Self-owned observe→serialize→think→act loop. |
| `chrome/browser/ai_agent/page_serializer.{h,cc}`  | `AnnotatedPageContent` → indexed `[i]<role>label` text + index→{dom_node_id, doc_id, bbox} map. |
| `chrome/browser/ai_agent/llm_client.{h,cc}`       | OpenAI-compatible chat/completions client. |
| `chrome/browser/ai_agent/humanized_mouse.{h,cc}`  | Bézier humanized click via `ForwardMouseEvent`. |
| `chrome/browser/ai_agent/agent_switches.{h,cc}`   | `--agent-llm-url/--agent-llm-key/--agent-model/--agent-tool-mode`. |
| `chrome/browser/ai_agent/BUILD.gn`                | `source_set("ai_agent")`. |
| `content/public/browser/web_contents_delegate.{h,cc}` | `RunAgentTask` virtual (content→chrome seam; default = unsupported). |
| `chrome/browser/ui/browser.{h,cc}`                | `Browser::RunAgentTask` override → `AgentController::Start`. |
| `chrome/browser/ui/BUILD.gn`                      | adds `//chrome/browser/ai_agent` dep. |

## IMPORTANT — the CDP command lives in `devtools/humanized-input.patch`

The `Browser.agentRunTask` command edits **four files already owned by
`devtools/humanized-input.patch`** (the repo rule is one upstream file per
patch), so those hunks are **not** in `agent-layer.patch`:

- `third_party/blink/public/devtools_protocol/domains/Browser.pdl`
  — appends `experimental command agentRunTask`.
- `content/browser/devtools/protocol_config.json`
  — adds `"agentRunTask"` to the Browser domain `include` + `async` arrays.
- `content/browser/devtools/protocol/browser_handler.{h,cc}`
  — `BrowserHandler::AgentRunTask(...)` resolves the target's `WebContents` and
    forwards to `WebContentsDelegate::RunAgentTask`.
- `content/browser/BUILD.gn`
  — adds `humanized_click.cc` to the content browser sources (this file is also
    edited by `humanized-input.patch` for the mac cursor overlay).

The agent's clicks go through `content::PerformHumanizedClick`
(`content/public/browser/humanized_click.h` + `content/browser/humanized_click.cc`,
in `agent-layer.patch`), which routes via `RenderWidgetHostInputEventRouter`
exactly like the fork's CDP `humanizedClick`. The public `RenderWidgetHost::
ForwardMouseEvent` was tried first and does NOT work — it delivers to the widget
without compositor hit-testing, so the DOM never sees a real click.

As of 2026-06-13 these four hunks **are** included in the checked-in
`devtools/humanized-input.patch` (regenerated from the working tree via
`git diff <UPSTREAM_REVISION> -- <files>` while intent-to-adding the new
files). The cursor/box visualization also moved that day: the agent now draws
an **in-page** overlay (`AgentController::ShowInPageOverlay`, an isolated-world
`position:fixed` box+dot in CSS-viewport px) instead of the macOS
`NSWindow`/child-view overlay — so it is correctly positioned on any display,
clipped to the page, and has no drop-shadow "glow". The native
`humanized_cursor_overlay_mac.{h,mm}` child-view path remains only for the CDP
`humanizedClick --visualize` flow.

## Runtime config

No GN args or `--enable-features` needed (`features::kGlicActor` is
`ENABLED_BY_DEFAULT` on desktop, not branded-gated). Launch with
`--disable-actor-safety-checks` plus the `--agent-llm-*` switches (see
`__tools/launch_agent.sh`, which reads them from `.env`).
