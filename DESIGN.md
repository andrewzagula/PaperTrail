---
name: PaperTrail
description: A local-first research workspace for reading, comparing, and building on papers.
colors:
  ground-dark: "#12141c"
  rail-dark: "#0e1016"
  panel-dark: "#151823"
  field-dark: "#171a24"
  ink-dark: "#e6e9f2"
  muted-dark: "#8b93a7"
  line-dark: "#232838"
  line-soft-dark: "#1b1f2c"
  line-strong-dark: "#39404f"
  periwinkle: "#8fa4ff"
  periwinkle-hover: "#a6b6ff"
  periwinkle-press: "#7488ea"
  complete-dark: "#5bd3a6"
  running-dark: "#e8b45a"
  failed-dark: "#e06c75"
  ground-light: "#f3f4f8"
  rail-light: "#eceef5"
  panel-light: "#ffffff"
  field-light: "#ffffff"
  ink-light: "#1b1e2b"
  muted-light: "#5e6577"
  line-light: "#dee1eb"
  line-soft-light: "#e7e9f1"
  line-strong-light: "#c3c8d8"
  indigo: "#4356c2"
  indigo-hover: "#3849a8"
  indigo-press: "#2f3d8f"
  complete-light: "#116848"
  running-light: "#7a570f"
  failed-light: "#b23c38"
typography:
  title:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  ui:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.08em"
  measurement:
    fontFamily: "Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.45
  code:
    fontFamily: "Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
  xl: "14px"
  full: "999px"
spacing:
  "2xs": "2px"
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  "2xl": "20px"
  "3xl": "24px"
  "4xl": "32px"
components:
  button-primary:
    backgroundColor: "{colors.periwinkle}"
    textColor: "{colors.rail-dark}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    typography: "{typography.ui}"
  button-primary-hover:
    backgroundColor: "{colors.periwinkle-hover}"
  button-primary-active:
    backgroundColor: "{colors.periwinkle-press}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-soft:
    backgroundColor: "rgba(143, 164, 255, 0.12)"
    textColor: "{colors.periwinkle}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.failed-dark}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  field:
    backgroundColor: "{colors.field-dark}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  field-focus:
    backgroundColor: "{colors.field-dark}"
    textColor: "{colors.ink-dark}"
  field-error:
    textColor: "{colors.failed-dark}"
  status-pill:
    rounded: "{rounded.full}"
    padding: "2px 8px"
    typography: "{typography.measurement}"
  tag:
    backgroundColor: "transparent"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
  panel:
    backgroundColor: "{colors.ground-dark}"
    rounded: "{rounded.lg}"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.muted-dark}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-selected:
    backgroundColor: "#1c2130"
    textColor: "{colors.ink-dark}"
---

# Design System: PaperTrail

## Overview

**Creative North Star: "The Quiet Workshop"**

PaperTrail runs on one machine, for one person, at `localhost`. The design assumes nobody else is coming. There are no avatars, no share affordances, no activity feeds, no account controls, no onboarding tour, and no empty-state illustration inviting a second user in. Every pixel of chrome that would imply an audience has been removed, and the removal is deliberate rather than unfinished.

That single-occupant assumption sets the density. This is a bench, not a showroom: tools are within reach and slightly close together, because the person using them already knows where everything is. Discovery results and library rows are dense and scannable; the paper breakdown and the implementation plan loosen into a real reading measure, because those are the two places a person stops scanning and starts reading. The interface never spends space on making itself legible to a newcomer at the cost of the person who uses it daily.

The second thing the workshop metaphor buys is honesty about work in progress. Long, failable operations are the normal case here, not the exception: fetching, parsing, embedding, ranking, and generating each take real time and each can fail halfway. The design treats a partially-failed run as a first-class state with its own layout rather than an error to hide, and every generated artifact carries a line saying a model wrote it. Nothing generated is allowed to look more settled than a hand-written note.

**Key Characteristics:**

- Two themes from one hue family, indigo and periwinkle, both first-class
- Instrument Sans throughout, Geist Mono wherever the interface reports a measurement
- Dense by default, loose only where reading actually happens
- Failure states name their fix, not just their fault
- Generated output always says it was generated
- Keyboard-first: the command palette is the primary way to move

## Colors

Two themes derived from one hue family. Light is not a translation of dark; both are authored, and the light values are deepened rather than tinted so neither mode reads as the afterthought.

### Primary

- **Periwinkle** (`#8fa4ff`, dark theme): the accent. Primary buttons, selected palette rows, focus rings, links, and the selection bar. Its light-theme counterpart is **Indigo** (`#4356c2`), deepened to hold 6.27:1 against white button text.
- **Indigo** (`#4356c2`, light theme): same role, same hue family, different luminance so it survives on a near-white ground.

### Neutral

- **Ground** (`#12141c` dark / `#f3f4f8` light): the page. Panels sit *on* it, not above it.
- **Rail** (`#0e1016` / `#eceef5`): the navigation surface. Darker than ground in dark mode, lighter in light mode, so the rail always reads as recessed chrome.
- **Panel** (`#151823` / `#ffffff`): panel headers and table headers only. Not a general card fill.
- **Ink** (`#e6e9f2` / `#1b1e2b`): all primary text.
- **Muted** (`#8b93a7` / `#5e6577`): secondary text, author lines, hints, labels. Both values clear 4.5:1 on their ground.
- **Line** (`#232838` / `#dee1eb`): container borders and group separators.
- **Line soft** (`#1b1f2c` / `#e7e9f1`): hairlines between peer items in a list.
- **Line strong** (`#39404f` / `#c3c8d8`): field borders and the hover border on interactive containers.

### Tertiary: status

Three colors, used only to carry the valence of a pipeline state. They never decorate.

- **Complete** (`#5bd3a6` / `#116848`): work that finished successfully.
- **Running** (`#e8b45a` / `#7a570f`): work in flight, and partial or stale results.
- **Failed** (`#e06c75` / `#b23c38`): work that stopped, and destructive actions.

### Named Rules

**The Measurement Rule.** Color is never the only carrier of meaning. Every status color is paired with a word, and disabled state is opacity plus cursor plus `aria-disabled`, never a color shift alone.

**The Accent Scarcity Rule.** The accent marks where a decision is available: the primary action, the current nav item, the focused element, a link. It never appears as ornament, never fills a header, and never tints a surface that is not interactive.

**The Contrast Floor.** Every text and background pair in both themes clears WCAG AA: 4.5:1 for body and small text, 3:1 for large. This has been verified for all thirteen screens; changing any color token requires re-checking it. Status colors were deepened specifically to pass at 11px pill size, which is where they are actually used.

## Typography

**UI Font:** Instrument Sans (with `system-ui, sans-serif`)
**Measurement / Code Font:** Geist Mono (with `ui-monospace, SFMono-Regular, Menlo, monospace`)

**Character:** Instrument Sans is neutral without being anonymous: slightly narrow, with enough character in the terminals to avoid the system-font look, and it holds up at 11px where most grotesques stop being legible. Geist Mono carries every number the interface reports. The pairing is quiet on purpose: the papers are the content, and the interface is the bench they sit on.

Two faces total. There is no display face, because there is no marketing surface in this product.

### Hierarchy

- **Title** (600, 21px, 1.3, -0.01em): the page heading. One per screen.
- **Headline** (600, 15px, 1.3, -0.01em): breakdown section heads on the reading screens only.
- **Body** (400, 14px, 1.65, max 68ch): breakdown prose, comparison narrative, chat. The one place the app steps up from 13px.
- **UI** (400, 13px, 1.45): everything else: buttons, rows, tabs, nav, settings labels, result titles.
- **Label** (600, 11px, 0.08em, uppercase): panel headers and palette section headers only.
- **Measurement** (400, 11px, mono, tabular-nums): counts, timings, dates, relevance scores, arXiv ids, chunk counts, keyboard hints, section citations.
- **Code** (400, 12px, mono, 1.45): pseudocode and starter files.

Nine size steps exist in the scale; no half-pixel values, and no size appears in a component that is not one of them.

### Named Rules

**The Uppercase Rule.** Uppercase with letterspacing is chrome, never content. It appears in exactly two component types: panel headers and palette section headers. A paper title, a status word, a button label, or a setting name is never uppercased.

**The Mono Rule.** Monospace means the interface is reporting a measurement or showing code. It is never a costume for looking technical. A status word is not a measurement, but it is set in mono anyway because it sits in the same column as the counts and must align with them. This is the one deliberate exception, and it is why status pills and scores share a size.

**The Reading Step.** Discovery and Library are triage and stay at 13px. The paper breakdown, the comparison narrative, and the implementation plan step to 14px with 1.65 leading and a real measure. Sustained reading gets a different setting from scanning.

## Layout

**Shell.** A wrapping flex row, not a grid. The rail is a fixed-width flex child and main is `flex: 1 1 0; min-width: 0`. This matters: container queries cannot restyle the element that *is* the container, so the shell's topology has to live on children the query can reach. A grid on the shell would make the responsive rules silently no-op.

**Rail width:** 208px expanded, 60px collapsed to icons, 100% when horizontal.

**Spacing scale:** 4px base with 2px and 6px half-steps for dense controls. Twelve steps: 2, 4, 6, 8, 12, 16, 20, 24, 32, 64, 80, 96. Every padding, margin, and gap resolves to one of these; there are no hand-picked values.

**Rhythm.** 24px body padding, 32px between groups inside it. The group gap is deliberately larger than the container padding. When they tie, a group stops reading as separate from its container. 12px inside a tight group, 20px between peer list items.

**Measure.** Reading columns cap at 68-74ch. Chrome and dense lists are uncapped.

**Responsive.** Container queries on the app shell, keyed to the shell's own inline size rather than the viewport, so a panel behaves the same whether it is the whole page or half of one. Two steps:

- **≤ 1040px.** The rail drops its labels to a 60px icon column; side-by-side panels stack; body padding drops to 20px; the settings control column narrows to 200px.
- **≤ 720px.** The rail moves to the top as a horizontally scrolling strip; the question field and its button stack; paper actions drop under the title and share the width; every settings row goes label-above-control at full width; the tab strip scrolls rather than truncating; the compare table scrolls inside its own box with the dimension-name column pinned.

Nothing is hidden at either step. Structure reflows; content stays, because there is no second place to go and find it.

**Nav orientation is a user setting**, not a breakpoint outcome. Sidebar and top bar are both first-class at every width above 720px; below it, horizontal is the only option and the setting is ignored.

## Elevation & Depth

The system is flat. Depth comes from tonal layering (rail darker than ground, panel lighter than ground, hairlines between peers), not from shadows.

There is exactly one shadow in the entire product.

### Shadow Vocabulary

- **Overlay** (`0 16px 48px rgba(0, 0, 0, 0.5)` dark / `0 16px 48px rgba(27, 30, 43, 0.25)` light): the command palette box, and any future modal. It is paired with a scrim (`rgba(5, 7, 12, 0.6)` / `rgba(27, 30, 43, 0.35)`).

The inset `box-shadow` used for hover and press is not depth. It is a color wash implemented as a shadow so that one token pair can tint transparent and filled surfaces alike while still animating. Do not read it as elevation and do not add offset or blur to it.

### Named Rules

**The One Shadow Rule.** If a surface is not floating above the page in the literal sense, meaning an overlay with a scrim behind it, it gets no shadow. Cards do not lift. Buttons do not lift. Hover does not lift.

## Shapes

Five radii, each with one job:

- **4px:** the smallest chips: keyboard hints, citation chips, checkboxes, focus-ring rounding.
- **6px:** every interactive control: buttons, fields, selects, nav items, segmented controls, steppers, code blocks.
- **10px:** containers that hold a group: panels, warning panels, the command palette box, the comparison table.
- **14px:** the outermost frames only.
- **full:** status pills and tags. Pill shape means "this is a label about something", and nothing else in the system is a pill.

Borders are 1px, always, in `line` or `line-strong`. There is no 2px border anywhere and no colored left-border accent stripe.

The one dashed border in the system is the PDF drop target, which becomes solid and accent-colored when a file is dragged over it. Dashed means "nothing here yet, put something here."

### Named Rules

**The Container Rule.** A box means one of two things: a discrete module, or an alert. Panels, warning panels, the command palette, code blocks, and the selection bar are boxed. Peer items in a list (discovery results, library rows, ideas, algorithm steps, assumptions) are never boxed. They get space and a hairline. If everything is a card, nothing is a module.

**No Nested Containers.** A panel does not contain a panel. If content inside a module needs separating, use a hairline.

## Components

The character across the board is *quiet and precise*. Controls do exactly what their label says, respond immediately, and never draw attention to themselves after the interaction is over.

### Interaction states: the whole system

Four moves. Which move an element uses is decided by what kind of element it is, and is not a per-component choice.

| State | Behaviour |
|---|---|
| **Hover** | An inset wash (`rgba(255,255,255,0.05)` dark / `rgba(27,30,43,0.05)` light), or a lighter/darker tint of the accent when the accent *is* the fill. Fields and outlined controls also raise their border to `line-strong`. Nothing moves. |
| **Press** | `scale(0.97)` on small controls; a deeper wash (`0.09` / `0.085`) on full-width rows. |
| **Focus** | A 2px accent outline. `outline-offset: 2px` on small controls, `-2px` on rows that run to a container edge, `1px` on fields, which also shift their border to the accent. |
| **Disabled** | `opacity: 0.45`, `cursor: not-allowed`, `aria-disabled="true"`. Overrides hover and press rather than sitting alongside them. |

**Rows do not scale on press.** Three percent of a 700px row moves its right edge 21px, which reads as a bug rather than a press. Buttons are small enough that the same 3% reads as the control giving way.

**Focus is never a background change.** Hover and focus must stay distinguishable, because a keyboard user and a mouse user can be the same person one second later.

Hover is gated behind `@media (hover: hover) and (pointer: fine)` so a touch device never leaves a hover stuck on the last thing tapped.

### Buttons

- **Shape:** 6px radius, 8px/16px padding, 13px/600. Small variant drops to 6px/12px.
- **Primary:** accent fill, accent-ink text. One per screen region.
- **Ghost:** transparent, 1px `line` border, ink text, 500 weight.
- **Soft:** `accent-soft` fill, accent text. Used for a completed or already-satisfied action ("View in library").
- **Danger:** transparent, 1px `line` border, `failed` text. Border goes `failed` on hover. **One red, one treatment.** The current codebase has two destructive buttons using two different reds, and that is the drift this rule exists to end.

### Fields

- **Style:** `field` background, 1px `line` border, 6px radius, 8px/12px padding.
- **Hover:** border to `line-strong`.
- **Focus:** border to accent, plus the ring.
- **Error:** border to `failed`, with a message below in `failed` at 12px carrying an alert glyph. **The message names the fix, not only the fault.** "That is not an arXiv address. Paste a link like arxiv.org/abs/1706.03762, or just the id on its own."

### Status, measurement, and category: three forms, three jobs

A reader can tell what kind of fact they are looking at before reading the words.

- **Status pill** (`.st`): filled, full radius, 11px mono. **Lifecycle state only**, and color carries valence. `complete` / `running` / `failed` / `idle`.
- **Score** (`.score`): plain 11px mono, no container. **A measurement.** Numbers are not states and do not get a pill.
- **Tag** (`.tag`): outline chip, full radius, transparent. **A category or a judgement, never a status.** Severity grades (`high` / `medium` / `low`) take this form with color for weight, so a severity never reads as a pipeline state.

### Navigation

- **Rail item:** 13px, muted, 15px icon, 8px gap, 6px radius. Selected gets `nav-on` fill and ink text.
- **Search trigger** sits directly under the top of the rail, not pinned to the floor. It is a primary way in, and the floor is where settings and sign-out go in products that have them. It shows icon, label, and the `⌘K` hint together, so it teaches the shortcut instead of only rewarding people who already know it.
- **No wordmark.** There is no logo anywhere in the shell.
- **Orientation** is a user setting: sidebar or top bar.

### Command palette

An overlay with a scrim, 480px, 10px radius, the one shadow. Sections labelled in uppercase 11px. Selected row takes `accent-soft` fill and accent text.

**The palette never animates.** It is a hundred-times-a-day action, and an entrance animation on it makes the whole app feel slow.

### Cards, panels, and list items

- **Panel:** 10px radius, 1px `line`, ground fill, `panel`-filled header at 11px uppercase.
- **Row** (`.rowi`): 12px/16px padding, `line-soft` hairline between, last child none.
- **Result / library / idea item:** unboxed. 20px vertical padding, `line-soft` hairline, a 32px index column for rank or a 16px column for a checkbox. Hover washes 12px beyond both edges via a pseudo-element, so the wash has breathing room against text that has no horizontal padding.

### Code

10px radius, `panel` fill, header strip carrying the file path in 11px mono and its purpose right-aligned in muted. Body is 12px mono with its own horizontal scroll. A collapsed file shows the header only.

### Motion

- **State transitions:** 120ms `ease`; transforms use `cubic-bezier(0.23, 1, 0.32, 1)`.
- **Theme swap:** 180ms `ease`, color properties only, never layout.
- **Spinner:** 0.7s linear.
- **Never animated:** the command palette, and any keyboard-initiated navigation.
- **`prefers-reduced-motion: reduce`** removes transitions and all transform-based press feedback.

Nothing in this product animates on scroll, and nothing has an entrance animation.

## Do's and Don'ts

### Do:

- **Do** take every spacing, size, radius, and color value from a token. Zero literals. The mockup deck has none, and the implementation should not introduce any.
- **Do** give every interactive element all four states. A component without a disabled state is unfinished.
- **Do** name the recovery in every failure message. "Provider returned 429 on 3 of 28 chunks → Retry the failed chunks", not "Embedding failed".
- **Do** label everything a model generated, at the point it appears, in 11px muted.
- **Do** use `.st` for pipeline states, `.score` for numbers, `.tag` for categories and judgements, and check which one you mean before reaching.
- **Do** put the actions beside the thing they act on. The paper page's actions sit next to the title, not in a rail.
- **Do** reuse the result-card shape for any ordered or checkable list of papers. A paper in Library and a paper in Discovery are the same kind of thing.
- **Do** keep both themes at AA and re-verify after any color change.

### Don't:

- **Don't** box a peer list item. Space and a hairline, always.
- **Don't** nest containers.
- **Don't** add a shadow to anything that is not an overlay with a scrim.
- **Don't** move an element on hover. No lift, no translate, no scale on hover.
- **Don't** scale a full-width row on press.
- **Don't** use a background change as a focus indicator.
- **Don't** uppercase content. Uppercase is chrome: panel headers and palette section headers, nowhere else.
- **Don't** use monospace as a texture for "technical". Mono means a measurement or code.
- **Don't** put a grid on the app shell. Container queries cannot restyle their own container, and the responsive rules will silently do nothing.
- **Don't** introduce a second red, a second accent, or a second icon family.
- **Don't** hand-author SVG icons. Pick one library and stay in it.
- **Don't** add avatars, share buttons, activity feeds, or account controls. Nobody else is coming.

---

## Appendix: Implementation State

Implementation mapping, not design doctrine. Every route below is built and running on the component layer; what remains is listed at the end.

### Routes

| Route | File | Notes |
|---|---|---|
| `/` | `frontend/src/app/page.tsx` | Question field, then recent runs and library side by side |
| `/discover/[id]` | `frontend/src/app/discover/[id]/page.tsx` | Polls while running; queries panel collapses |
| `/library` | `frontend/src/app/library/page.tsx` | Every paper, with search, sort, status filter, and bulk actions. `/dashboard` redirects here, see `next.config.ts` |
| `/library/saved/[id]` | `frontend/src/app/library/saved/[id]/page.tsx` | One viewer for comparisons, idea sets, and plans |
| `/papers/new` | `frontend/src/app/papers/new/page.tsx` | arXiv field and drop target, either one ends the same way |
| `/papers/[id]` | `frontend/src/app/papers/[id]/page.tsx` | Breakdown, Chat, Sections; Implement is a link, not a panel |
| `/papers/[id]/implement` | `frontend/src/app/papers/[id]/implement/page.tsx` | One continuous page, no tabs |
| `/compare` | `frontend/src/app/compare/page.tsx` | Picker, then narrative summary and matrix |
| `/ideas` | `frontend/src/app/ideas/page.tsx` | Picker plus optional topic, then ranked ideas |
| `/settings` | `frontend/src/app/settings/page.tsx` | Providers, models, per-step models, and appearance. Backed by `/settings` on the API |

Workspace is gone from the nav. Saved work is reached from the section that produced it, and the saved viewer serves all three kinds.

### How settings are stored

`.env` records how the machine was set up. Choices made in the Settings screen live in `data/settings.json` and are layered on top at startup and on every change, so the two never fight and reverting is deleting one file. `backend/app/services/app_settings.py` owns validation, the atomic write, and dropping the cached provider clients so a change lands without a restart.

A per-step model stored as `null` means *follow the chat model*, and it keeps following when the chat model changes. On the settings object that resolves to an empty string, because the provider clients already read an empty model as "use the default" and one convention for an idea is enough.

### Component layer

`frontend/src/components/`, exported through `@/components`. Import from the barrel, never from the files underneath.

**Shell**, in `components/shell/` (`AppShell.tsx` and `CommandPalette.tsx`)

| Component | Notes |
|---|---|
| `AppShell` | Wrapping flex row, `container-type: inline-size`. Owns both responsive steps. |
| `TopBar` | Breadcrumb left, arbitrary right slot. |
| `Body` | The padded page column. Takes `col-narrow` or `col-mid` to set the measure. |
| `CommandPalette` | Overlay search over papers, saved work, and runs, plus a fixed Actions list. Opens on the rail trigger or on Cmd/Ctrl+K, which `AppShell` binds to the document. |

The palette has no backend behind it. It fetches `GET /papers/`, `GET /workspace/saved-items`, and `GET /discover/` whole on every open and filters them in the browser, which for one person's library on one machine beats a round trip per keystroke. Every row is somewhere to go; nothing in it spends tokens or deletes anything, so Enter is always safe to press without reading first.

**Controls**, in `components/ui/controls.tsx`

`Button` (primary / ghost / soft / danger, `sm`), `Input`, `Field`, `Select`, `Menu`, `Segmented`, `Stepper`, `Checkbox`, `Dropzone`, `Tabs`.

`Select` is a trigger only, for cases where the caller owns the menu. `Menu` is a native `<select>` wearing the same clothes, and it is the default: keyboard handling, typeahead, and the small-screen picker all come free, and none of them are worth rebuilding.

**Display**, in `components/ui/display.tsx`

`StatusPill`, `Score`, `Num`, `Tag`, `Cite`, `Kbd`, `Provenance`, `Spinner`, `Working`, `Stage`, and `toneFor()`, which maps a backend status string to a tone so no page invents its own mapping.

**Layout**, in `components/ui/layout.tsx`

`PageHeader`, `Section`, `SectionHead`, `Split`, `Toolbar`, `Panel`, `PanelHead`, `PanelBody`, `Row`, `WarnPanel`, `SelectionBar`, `CodeBlock`, `Item`, `Step`, `GapItem`, `PlainList`.

`WarnPanel` takes an optional `actions` slot. An alert that can name a fix should be able to carry it, rather than describing a problem and leaving the person to go find the button.

**States**, in `components/ui/states.tsx`

Loading, absence, and failure are states this product spends real time in, so they are designed rather than improvised: `Blank`, `Empty`, `Skeleton`, `PageSkeleton`, `Chip`, `ChipRow`, `Fact`, `Facts`, `Confirm`, `Notice`.

### Embedding state, and why it is on screen

Embeddings are tracked per paper, per provider, and per model, so changing the embedding model in Settings destroys nothing: the old vectors stay where they are and the paper reads as `stale` until it is embedded again with the model now in force. `frontend/src/lib/embedding.ts` holds the four statuses and the sentence each one deserves, so Library and the paper page say the same thing about the same state.

That state is only worth tracking if it is fixable, so re-embedding is offered in three places, all of them backed by endpoints that already existed:

- The **paper page** carries a `WarnPanel` naming the fault and the fix, because that is where a person notices: they open a paper to chat with it and the answers stop lining up.
- **Library** shows a `WarnPanel` above the list counting every paper that is out of step, and a `Re-embed` button on each row that needs one.
- The **selection bar** re-embeds a hand-picked set. That request sends `force: true`, since the papers were chosen deliberately and a button that can silently decide to do nothing is worse than one that costs a few tokens. The warning panel's button sends `force: false`, which is the API's word for "only what is out of step".

Re-embedding costs money, so nothing does it automatically and every control that triggers it says so first.

### Density

Density is a user setting and it changes the vertical rhythm only: `--row-y`, `--item-y`, `--sec-gap`, `--body-pad`, `--bar-h`. No type sizes, no horizontal measure, no colours. Reading size is a separate control, because shrinking the interface and shrinking the prose you are trying to read are different wishes.

Anything that sets its own vertical padding should reach for one of those five tokens rather than a raw spacing step, or it will sit still while the rest of the page tightens.

### Two rules worth restating, because both were nearly broken during the migration

**Severity and feasibility run in opposite directions.** A high-severity gap is the one to look at first, so it takes the alarm grade. A high-feasibility idea is the safe one, so the alarm grade goes to *low* feasibility. The inversion lives in one map per page, never at the call site.

**A chip navigates; a tag describes.** They look similar and mean different things. `Chip` is a pointer to another record and carries hover, press, and focus. `Tag` is a category or a judgement and is inert.

### What is not done

- **API keys.** Deliberately not editable from the web layer. `/settings` reports which keys each provider needs and whether this machine has them, and points at `.env` for the rest. Nothing in the settings path reads, returns, or accepts a credential.
- **Staged ingest progress.** `/papers/new` names what it is doing in one line because the backend ingests in a single blocking call. The four-stage list in the deck needs progress events first.
- **`/compare/[id]` and `/ideas/[id]`.** The saved viewer already serves all three kinds from `/library/saved/[id]`; the friendlier paths are not routed yet.
