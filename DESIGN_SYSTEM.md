# Belong UI design system

This document turns Belong's UI principles into a small, enforceable visual system.
It is intentionally lightweight: native HTML semantics, Django templates, and
Tailwind utility/component classes. Do not import a prefab design system that
overwrites Belong's visual identity.

The system is anchored in:
- native HTML semantics and WAI-ARIA Authoring Practices for buttons, disclosures,
  menus, radio groups, and stateful controls;
- WCAG 2.2 target-size/accessibility requirements;
- Tailwind's spacing/sizing scale rather than arbitrary one-off dimensions;
- Belong's existing purple/teal/slate palette, Rockwell display type, Inter/system
  body type, rounded shapes, warm/lightweight tone, and dense activity-card model.

## 1. Core geometry

Use a 4px baseline grid. Prefer Tailwind spacing values rather than arbitrary pixels.

Standard spacing:
- 4px: internal micro-spacing only
- 8px: related controls/items
- 16px: separation between control clusters
- 24px: section spacing
- 32px+: major structural separation only when content warrants it

Page gutters:
- mobile: 24px
- small/tablet: 32px
- desktop: 40px

Search/discovery controls, activity result utilities, card grids, and floating
primary actions should align to the same content gutter unless a deliberate
secondary region such as Who's around is present.

## 2. Interactive target sizes

Belong exceeds WCAG's 24x24 CSS pixel minimum for ordinary controls.

Use these Tailwind-aligned heights:
- compact control: 36px (`h-9` / `min-h-9`) — dense card/footer use only
- standard control: 40px (`h-10` / `min-h-10`) — normal UI default
- comfortable/touch control: 44px (`h-11` / `min-h-11`) — forms and prominent actions
- floating primary action: 48px (`h-12 w-12`)

Do not create tiny one-off controls below the compact standard.

## 3. Shape and borders

Belong uses soft rounding, but shape communicates semantics.

- standard fields/buttons/disclosures/menu triggers: rounded-xl
- compact card controls: rounded-lg or rounded-xl
- segmented controls/filter chips: rounded-full is acceptable because the grouping
  itself communicates state
- floating + action: circle
- border weight: 1px standard
- avoid mixing three different radii in one control cluster

Pills are not the universal answer. Reserve them for chips, segmented state choices,
and genuinely pill-like compact filters.

## 4. Control families

Implement reusable component classes in `assets/tailwind.css` under
`@layer components`. Templates should prefer these families over repeated
one-off utility recipes.

### Primary action
Purpose: the main immediate action in a context.
Visual: Belong purple fill, white text, standard/comfortable height.
Examples: Search, Create group, Apply filters when it is the clear commit action.

### Secondary action
Purpose: real action, lower emphasis.
Visual: white/transparent background, purple border/text, same height/radius family
as peer primary actions.
Examples: Leave group, secondary form actions.

### Quiet action
Purpose: reversible/private/infrequent mutation.
Visual: still unmistakably a control; compact border/background treatment.
Never plain underlined text pretending to be a button.
Examples: Hide/Unhide.

### Navigation link
Purpose: go somewhere.
Visual: text/link treatment, normally underlined or otherwise consistently
recognizable as navigation.
Examples: Details, Back to Discover, group name link.

### Menu trigger
Purpose: open a set of secondary actions/navigation.
Visual: standard control family plus chevron/disclosure cue.
Use real menu/disclosure semantics; do not hide primary actions in menus.

### Disclosure
Purpose: expand/collapse content in place.
Visual: standard or compact control with chevron and explicit expanded state.
Examples: Advanced filters.

### Independent boolean filter
Purpose: a genuinely binary on/off dimension that may coexist with peers.
Use checkbox semantics with a consistent filter-chip visual family and obvious
selected state. Do **not** use a row of boolean chips when the underlying concepts
are really multi-valued filter dimensions.

### Discovery facet menus

Discovery filters are **faceted multi-select menus**, not ordinary single-select
dropdowns.

Each visible facet is one compact menu trigger. Opening it reveals independent
checkbox choices. The user may select zero, one, or several choices within a facet.

Semantics:
- zero selections in a facet = no restriction for that dimension; do not add fake
  `Any` / `Anywhere` choices just to represent the empty state
- multiple choices within one facet combine with **OR**
- different facets combine with **AND**
- changes apply immediately
- free-text search remains explicit and submits only on Search/Enter
- the closed trigger must visibly summarize active state (for example a short value
  when one choice is selected, or a count when several are selected)
- menus must use native checkbox semantics and remain keyboard/touch accessible

Current visible facets:

**When**
- Now
- Today
- Tomorrow
- This week
- This weekend
- Open-ended

**Where**
- Online
- Under 1 mile
- 1–3 miles
- 3–5 miles
- 5–10 miles
- 10–25 miles
- 25+ miles

Distance buckets represent approximate physical distance from the user's location.
In-person activities match the appropriate distance bucket. Hybrid activities may
match both Online and their physical-distance bucket. Activities without usable
coordinates cannot match a distance bucket.

**Cost**
- Free
- $ = $1–10
- $$ = $11–25
- $$$ = $26–50
- $$$$ = $51–100
- $$$$$ = $100+

Use the dollar-sign count as the visible shorthand in compact filter UI. Keep the
underlying numeric ranges explicit in labels/tooltips/accessibility text where useful.
When an activity has a known exact cost, the card should prefer the actual human-readable
amount rather than replacing it with only the tier shorthand.

Cost is an accessibility dimension, not merely Free/Paid decoration. Filtering must
be backed by structured numeric cost data; do not infer tiers by parsing arbitrary
display text. Preserve a human-readable cost display for card copy, but add structured
numeric amount/range data to the activity model/forms as needed. Unknown/unstructured
cost does not silently match a numeric tier.

**Open to**
- Everyone
- Friends only
- Friends of friends

Free-text search answers the primary **what** question. Category remains part of the
data/search model but is not a permanently visible discovery facet by default.

The product does **not** need an Advanced filters panel while these facets cover the
active discovery dimensions. Hidden activities remain private list-management state
with a separate quiet recovery control.

### Discovery toolbar layout

Discovery controls should read as one compact toolbar, not several unrelated rows.

Desktop target:
- search field + Search
- When / Where / Cost / Open to facet triggers
- Stacked / Spread out view selector
- quiet hidden-activity recovery only where it can fit without forcing an otherwise
  unnecessary row

Use the standard 40px control height and consistent 8px gaps within a row. Prefer one
row when the available content width permits. When wrapping is necessary, wrap by
semantic cluster with the **same row gap and vertical rhythm**; do not create three
unevenly spaced bands through arbitrary margins/padding.

Search should consume flexible width; facet triggers and view controls should remain
content-sized. On narrow mobile layouts, deliberate wrapping is expected, but rows
must still align cleanly and use consistent spacing.

This tiered model is intentional: Belong is designed for people whose mobility and
means may be constrained. A free or $5 activity within a mile is materially different
from a $100 activity several miles away; the interface must preserve that distinction
rather than collapsing cost to Free/Paid or distance to Nearby/Not nearby.

### Mutually exclusive view selector
Purpose: choose exactly one display mode.
Use radio/segmented semantics and an obvious selected segment.
Examples: Stacked / Spread out.

## 5. Typography

Preserve current Belong type:
- display/headings: Rockwell family fallback stack
- body/control text: Inter/Segoe UI/system

Hierarchy:
- page title: display face
- activity title: strongest card text
- metadata: body face, smaller but fully legible
- controls: body face, consistent weight within a control family

Do not use all-caps tracking as generic decoration. Reserve it for rare compact
labels where it materially improves hierarchy.

## 6. Color

Keep the existing Belong palette authoritative.

- primary action/identity: belong-purple
- stronger hover/emphasis: belong-purpleDark
- positive/accent: belong-teal
- neutral text/meta: belong-slate
- page background: belong-background
- white/translucent white for card/control surfaces

Do not introduce unrelated blue/gray component-library colors into normal product UI.

Color cannot be the only state indicator. Selected/pressed controls must also expose
state through fill, border, text, shape, check/radio state, or another visible cue.

## 7. Activity-card architecture and information hierarchy

The historical Belong card prototypes are the visual/product reference for card
architecture. Preserve their useful structure while applying the current design
system and current product semantics.

### Overall proportions

The card is a portrait-format scanning object. The current width is useful; allow
the standard card to become somewhat taller so information and actions do not fight
for space.

Use **approximately 440px standard height at the current preferred desktop width**
as the next baseline. Tune only through browser review; do not widen a card merely
because result count is low. The target should remain comfortable on modern phones.

### Band 1 — activity identity

Band 1 contains:
- the **activity/event name**
- a visually minimal contextual `⋮` trigger in the top-right corner

#### Title layout

- title is the dominant card text, but should feel **calm rather than heavy**; use the
  normal Belong body sans stack for card titles with medium weight rather than a
  visually dense semibold/bold treatment
- start around **20px / 24px line-height / medium weight** at the current card width;
  use the existing bounded step-down strategy only for genuinely long titles
- allow **up to two title lines**
- keep Band 1/card geometry stable; do not grow the card merely because content is long
- for longer titles, strategically step down through a small bounded type scale before
  clipping (for example normal / slightly reduced / minimum readable size)
- if the title still does not fit the two-line budget, clamp at two lines and show an
  ellipsis rather than clipping glyphs or colliding with logistics
- use sufficient line-height/leading for descenders at every supported title size
- center the title in a fixed 48px title zone inside the 64px band
- Title Case is an authoring convention, never CSS text-transform; preserve acronyms
- reserve a small symmetric safe inset at both left and right so the top-right menu
  trigger does not overlap or visually push the centered title off-axis

#### When/where layout (Band 2)

Treat when and where as **two structured atomic values**, not one arbitrary wrapping
string.

- allow up to **two logistics lines total**
- if `when · where` fits cleanly on one line, show it on one line
- if it does not fit, place **when on one line and where on the next** rather than
  allowing one value (especially location) to wrap messily across both lines
- use **13px / 16px line-height / regular weight** for metadata and logistics;
  truncate long values rather than shrinking the text
- if an individual value still exceeds its line budget, truncate with ellipsis and
  expose the full value on hover/focus
- do not use the generic `headline` field as a card subtitle

When and where remain the most important first-pass facts after the activity name.

#### Contextual menu trigger

The card's single contextual menu trigger lives in the **top-right of Band 1**.

- use a **vertical kebab `⋮`**, not a horizontal ellipsis; horizontal dots visually
  collide with centered/truncated title text and read too much like punctuation
- visual treatment: white, initially somewhat subdued (70% opacity, 20px glyph), with
  no visible pill, border, or filled button chrome in the resting state
- hover/focus raises the glyph to full opacity
- offset only the visible glyph 4px right within its unchanged transparent hit target
- semantic treatment: still a real keyboard/touch-accessible button/disclosure with
  an adequate transparent hit target and visible focus state
- the trigger must not overlap title/logistics text; reserve layout space for its hit
  target while preserving visual centering of the text
- the opened menu may float above card content temporarily; this does not authorize
  any persistent control overlay in the image band

Recommended menu contents:
- More from this organizer
- More at this time
- More at this place
- More in this category
- divider
- Hide this activity
- Hide this organizer's activities

The first four commands keep the user in Discover and change discovery context rather
than sending them into the activity Details room. `Hide this organizer's activities`
is a private discovery preference, not a full user block.

Use a restrained horizontal light-left → dark-right header gradient derived from
the existing palette. Darken the primary to meet 4.5:1 white-text contrast; blend
25% accessible secondary into the right endpoint, darken 15%, and cap its RGB
channels at 85% of the left endpoint. All interpolated colors retain contrast.

#### Creation-time fit guardrails

Do not rely solely on runtime truncation. Activity creation/editing should guide
authors toward card-safe values.

- impose a practical card-title limit in the form layer rather than exposing the
  model's much larger storage limit as the normal authoring allowance
- provide a visible character counter and warning before the hard limit
- apply similar guidance to the short location/venue label used in Band 2
- structured date/time fields should generate compact display text automatically
- longer descriptions, addresses, instructions, and marketing copy belong on Details,
  not in Band 1

Character limits are guardrails, not a substitute for rendering safeguards: cards
must still clamp/ellipsis safely because glyph widths and mobile widths vary.
### Band 2 — practical/social context

The 72px Band 2 contains up to four deliberate 13px / 16px lines, in this order:
1. organizer (normal weight)
2. when / place, combined only when both fit
3. second logistics line only when needed
4. audience / cost

Use two columns: a fixed 44px circular avatar, vertically centered against the
entire metadata block, and one aligned text column with an 8px gap. Band 2 uses
2px vertical and 8px horizontal padding. Never stretch the avatar.
Each field uses a single-line ellipsis with full-value hover/focus. No empty
placeholder rows; unresolved facts use meaningful Date TBD / Location TBD text.
Without JavaScript, when and place occupy separate bounded lines.

Core decision facts must be understandable without hover/focus. Shorten presentation,
rebalance lines, or remove decoration before truncating essential meaning.

Use explicit unresolved states such as Date TBD, Location TBD, Online, Cost TBD.

### Band 3 — image

Band 3 is the activity image. **Do not overlay controls, dropdowns, menus, counts,
badges, or platform utilities on the image.**

The image remains a major visual element and should not be cannibalized to make room
for controls. Preserve roughly the original/prototype visual prominence.

Artwork uses `object-cover`, so some cropping is inherent. Do not shrink the image
viewport so far that normal subject matter is routinely cut off.

### Band 4 — useful description

Band 4 should have enough height for several useful lines of description.

- Content is **top-aligned consistently** across all cards; do not vertically center
  short descriptions.
- Prefer roughly 4–6 readable lines at standard card size.
- Do not spend this band on a generic subtitle/headline.
- Do not place activity CTAs such as `Join on Discord`, `Hold my spot`, RSVP,
  payment, or similar actions as stray body hyperlinks. If an action deserves a
  card-level shortcut, it belongs in Band 5; otherwise it belongs on Details.

### Band 5 — take action

Band 5 is reserved for **one or two actions specific to this activity**.

Examples from historical prototypes include:
- I'm interested
- Tell me more
- Join on Discord
- Join the club
- Not for me

Rules:
- maximum two primary actions on the card
- labels must be fully readable; never ellipsize action labels
- actions use one coherent button geometry/family
- **do not use global Belong purple as the default card-action color**; Band 5 should
  inherit the activity/card palette
- default unselected action: white/translucent surface with border/text derived from
  `--card-primary` (or another explicitly defined accessible card accent)
- Band 5 uses the same accessible horizontal gradient as Band 1
- selected card action: white surface with card-local accent text, an inset 2px
  accent border and underline; selection must remain visible without color alone
- focus-visible: a white 2px outline with 2px offset against the colored footer
- **a checkmark is status, not decoration**: render `✓` only when the user's current
  response is a genuinely confirmed/committed state such as RSVP yes / Count me in
- a softer selected state such as Interested uses the selected border/underline
  treatment without a checkmark
- question/vote/external/CTA buttons never receive a checkmark merely because they are
  available actions
- if a card palette cannot provide accessible contrast, use a documented accessible
  fallback derived for that card rather than silently reverting the entire footer to
  generic purple
- peer actions on the same card must use the same card-local accent system
- stateful response actions expose selected state
- external/action links rendered as primary activity actions may use the same
  footprint but must expose their navigation/external semantics appropriately
- do not place Details, Hide/Unhide, generic Actions, response counts, or other
  platform utility controls in the take-action band
- if the activity has more than two possible responses/actions, choose the one or
  two most useful direct actions and expose the rest on Details

Platform utilities are secondary to the activity itself:
- Details is available through the title/card navigation pattern
- Band 1 exposes the defined contextual three-dot menu for repeated Discover-room
  operations such as related-activity exploration and hiding
- do not create additional generic utility menus elsewhere on the card merely to
  house leftover controls
- response removal, payment, questions, voting, and other richer interaction belong
  on Details unless explicitly promoted to Band 5 as a high-value shortcut
- response counts are information, not actions, and need not appear on the compact
  discovery card

The card should visually answer:
**What is this? Who is it for? When/where is it? What will it cost? What can I do?**

## 7A. Activity-card sizing and grid behavior

Activity cards are fixed-format scanning objects, not fluid content panels. Their
visual proportions must remain stable as the result count changes.

- Define a preferred/max card width from the existing card layout variables/design tokens.
- A single matching activity must render as one normal-width card; it must **not**
  stretch to fill the entire activity-results frame.
- Card/grid columns may become narrower down to the defined mobile/minimum width when
  needed, but must not grow beyond the intended desktop card width merely because
  fewer results are present.
- The grid should pack as many normal-width columns as fit and leave unused horizontal
  space rather than inflating cards.
- Keep the first card/column aligned to the activity-results frame rather than
  centering a lone card in a way that breaks alignment with search/results controls.
- Stacked and Spread out modes use the same underlying card width; view mode changes
  overlap/layout only, not card proportions.
- **Stacked mode must expose all of Bands 1 and 2 on every card in the pile.** The
  stack offset should therefore equal (or closely track) the combined height of the
  first two bands. A covered card must still reveal activity name, when/where,
  organizer, audience, and cost.
- Filtering from many results to one or zero must not cause surrounding controls,
  Who's around, gutters, or card geometry to jump unpredictably.

## 8. Activity-card actions and secondary utilities

The take-action band follows Band 5 rules above. Secondary platform controls must
remain secondary and must not re-enter that band.

- current selected response must be visible
- clicking a selected direct response may clear it
- if a historical/current response is no longer directly offered, show that state
  coherently on Details rather than cluttering the compact card
- use the single Band 1 contextual menu for repeated Discover-room operations
- richer/infrequent interaction that does not support repeated card scanning belongs
  on Details
- do not place menu triggers or utility overlays in the image band
- do not mix response buttons, menu triggers, tiny mutation controls, and navigation
  links in one row merely because they all happen to be clickable

Compactness comes from hierarchy and omission, not from shrinking random controls.

## 9. Forms

- labels visible except where a conventional search field placeholder plus accessible
  label is sufficient
- related controls grouped
- progressive disclosure preferred over long flat forms
- standard field height/radius/border family
- help text only when it changes successful use

Group access uses `ui-radio-choice`: native radios in a fieldset with an explicit
legend, a full descriptive label and a visible selected border/background. Create
workflows suppress the global + and remain full-page forms. Group-scoped activity
creation shows its context above the main fields; image defaults seed new records.

`ui-choice-list` groups independent response checkboxes with 40px labels; each
input retains `ui-check` rather than inheriting the container grid class.
Series uses the same focused full-page form and control families. Creating an
occurrence names the source Series and associated Group above the main fields.
It edits a copy of the defaults; cadence metadata describes the pattern without
claiming automatic scheduling. Series management stays with its organizer context.

## 10. Responsive behavior

Mobile is designed, not compressed.

- no horizontal overflow at 320/375px
- primary task remains first
- controls may wrap by semantic cluster
- do not split tightly related controls across distant rows
- secondary content may use a mutually exclusive pane switch on narrow screens
- card top-band information remains visible on mobile

### Discover panes

Discover has one Friends list and one Activities pane, regardless of result count.
At 1024px and wider, both panes fill the space beneath the shared header and scroll
independently. A 24px-wide vertical separator provides a visible dividing line and
a comfortable drag target. Friends defaults to 240px, clamps between 200px and
420px (leaving room for two activity cards), and remembers the chosen width locally.
The focusable separator exposes its range and current width; Left/Right adjust by
16px, Home selects the minimum, and End selects the available maximum.

Below 1024px, the existing `ui-segmented` radio family switches between Activities
(default) and Friends above the panes. Only the selected pane is visible; filters,
card view, results, and each pane's scroll position survive switching. Header and
floating Create stay available. Each pane reserves bottom clearance for Create.
Without JavaScript, both sections remain available in normal document flow.

## 11. Accessibility semantics

Prefer native elements first.

- action => `button`
- navigation => `a`
- independent boolean => checkbox
- mutually exclusive choice => radio group
- disclosure => button/details semantics with expanded state
- menu trigger => explicit menu/disclosure trigger

Keyboard focus must be visible. State must be exposed to assistive technology and
visually apparent.

## 12. Implemented discovery facets

`ui-facet` wraps a native details/summary trigger and checkbox fieldset. The
`ui-facet__panel` uses the menu family; `ui-facet__option` has standard 40px
checkbox targets. Triggers show a selected count (or the cost shorthand) and an
active border/background. Mobile uses two columns; desktop uses a compact cluster.
Checkbox changes submit immediately and preserve the applied search text, open
facet and keyboard position. Search/Enter commits text. Without JS, Apply filters
submits the same checkbox values. Search, facets and view/recovery clusters use
one wrapping `discovery-toolbar`, 40px controls and uniform 8px gaps. The view and
quiet Show hidden controls wrap together, so recovery never occupies its own row.

Repeated `when`, `where`, `cost`, and `audience` parameters are the canonical
facet state and survive pagination and response changes. Empty facets are unrestricted.
Now means an event currently between its start/end, a start within the last two
hours with no end, or explicit dateless `Now` intent. Today/Tomorrow use the pilot
local calendar; This week runs from today through Sunday; This weekend covers the
current or next Saturday/Sunday. No arbitrary time prose is parsed.

Physical distance buckets are [0,1), [1,3), [3,5), [5,10), [10,25), [25,infinity)
in miles. Only in-person/hybrid activities with valid coordinates match them.
Online/hybrid match Online; OR permits both modes. Geolocation denial clears only
distance choices, preserving Online and other facets with visible feedback.

`cost_amount` is an optional nonnegative exact USD amount. Paid tiers use positive
amounts through 10, then (10,25], (25,50], (50,100], and over 100, keeping decimal
prices and boundary values disjoint. Free uses explicit free cost type. Forms
reject contradictory free/paid/unknown numeric costs. Arbitrary cost display text
and unknown numeric amounts never determine tiers. Exact/display costs remain on
cards. Only matching tracked, owner-preserved authored demo prices are populated.

## 13. Implemented card patterns

- Geometry: 440px height, preferred/max width 258px, 64/72/128/128/48px bands.
  The 136px stack offset reveals all identity/logistics and participation context.
- Card title: `activity-card__title-link`, hover/focus navigation without a resting
  underline. `card-fit.js` uses bounded 20/24, 18/22, 17/22px size/leading pairs at medium
  weight,
  then a two-line ellipsis. Title width reserves symmetric 40px outer insets for
  the top-right 36px transparent vertical-kebab trigger. Band 1 has a fixed
  48px title zone with 8px vertical padding; short titles center in that zone. The
  20px white kebab rests at 70% opacity and becomes fully opaque on hover/focus.
- Band 2 logistics: structured when and where share one line only when they fit at 13px.
  Otherwise each receives the full line width at 13px / 16px leading,
  with individual ellipsis. Full title/when/where values remain available on
  hover/focus. Font loading, resize and HTMX replacement trigger refitting;
  without JS, the two-line title and separate logistics rows remain bounded.
- Primary responses: `ui-button ui-button--compact ui-response ui-response--card`,
  complete 12px labels. Card-local `--card-accent` derives from the primary palette:
  retain colors with at least 4.5:1 contrast against white, otherwise darken RGB
  channels together by 10% steps until they meet that ratio. Invalid colors use
  neutral #333333. White card controls use accent text/borders in both states; selected
  controls add an inset 2px accent border and a 2px underline without changing
  their geometry. White focus outlines contrast with the shared Band 1/5 gradient. `ui-response--confirmed` supplies the
  checkmark only for an actual selected `committed` response, on cards and Details.
  Interested, question, more, vote, declined and external actions have no check.
  General application actions stay purple.
  The first choice works without JavaScript. `card-actions.js` exposes a second
  choice only when both full labels plus any possible committed-state check fit.
  Remaining choices stay available on Details. HTMX refreshes the entire card's state.
- `activity-card__context` has two columns: a fixed 44px circular avatar centered
  against the entire three/four-line metadata block, and aligned text. The image never stretches. The
  single contextual trigger is in the top-right of Band 1. Known numeric
  prices / Free use concise metadata; longer names/cost prose expose full text
  on hover/focus; every metadata value stays on one deliberate line. The single native
  `card-context-menu` contains related Discover links and private hiding. Escape
  and clicking outside dismiss it; it remains usable without JavaScript.
- Band 3 contains only the activity image or fallback artwork. No controls,
  counts, badges or platform overlays appear in the image band.
- Details navigation uses the title link. Response counts, removal and richer
  participation live on Details; activity/organizer hiding also lives in the Band 1 menu.
- Current response: the first direct response exposes pressed state. A
  `card-current-response` line in the body identifies later/historical choices,
  including a second choice that might not fit. Removal is available on Details.
- The 128px top-aligned description band uses the same 13px body size as Band 2,
  with relaxed 18px leading and up to six lines; a current response reserves a line. External CTAs and the generic headline stay on Details.

### Truncated card text

Card text stores complete values in `data-full-text`, never native `title`.
`full-text.js` enables its tooltip only when the rendered text exceeds its box
(scroll width/height, with a 1px tolerance). Title links are measured against the
clamped headline box and keep native link focus; noninteractive text enters the
tab order only while clipped. Summary and description render full values and let
CSS clamp them, so layout measurements reflect actual truncation.
Font loading, resize, card layout/refitting and HTMX replacement recheck clipping.
Escape, scrolling, resizing and replacement dismiss the tooltip. Ordinary visible
text produces no tooltip and adds no metadata tab stops.

### Form fit guardrails

`ActivityForm` limits titles to 48 characters and short venue labels to 40; model
storage stays at 160/200 to preserve legacy data. These limits apply to new and
instance-bound forms. Inline character counters warn at 80% (39/48 and 32/40),
with HTML maxlength and server validation. Longer copy belongs in descriptions,
structured addresses and instructions. Browser comparison of normal prose and
wide/narrow glyph strings informed the limits; runtime fitting remains necessary.

## 14. Contextual Discover operations

Context links retain applied search, repeated facets and other context, reset
pagination, and AND with current filters. Each active context has an independent
clear link; toolbar submissions, pagination and response forms preserve it.
`organizer` is the activity's actual host account. `context_time` / `context_place`
refer to a visible source activity: scheduled time matches its pilot local calendar
day, dateless time matches the same explicit timing text; physical place matches
its supplied structured location fields (or exact valid GPS when those are absent).
Online place matches online/hybrid. Category uses the existing category slug.
Unresolved time/place/category commands are omitted rather than inventing context.
Invisible/missing source context cannot reveal private activities.

`HiddenOrganizer` is a private, unique viewer/host preference, separate from
friendship, user blocking and activity responses. Default Discover excludes both
individually hidden activities and suppressed organizers; Show hidden includes them
and the menu offers Unhide. Unhiding an organizer does not clear activity-specific
hiding. No accounts or response data are changed by suppression.

## 15. Review rule

A UI change is not complete if it merely "works."

Before presentation, review:
- semantic role
- control family
- height/radius/border consistency
- spacing/alignment
- selected/disabled/expanded state
- mobile behavior
- card information hierarchy when applicable

If a new visual pattern is needed, add it here first rather than inventing it locally.


## Account identity and settings

Signup uses email, password confirmation, the existing `ui-radio-choice` family for
Individual/Organization, and a required display name. Account settings reuses these
controls with separate Profile and Email sections; email changes use a distinct
password-confirmed form. Optional home area copy requests locality/postal code,
never a street address. Profile image controls use the standard field/button family.
Verification pages expose only verification and logout; product navigation and
Create remain hidden until access is granted. Settings and password forms suppress
Create to keep their task focused. Display names replace opaque usernames in public
identity, with an explicit “(Organization)” suffix wherever that identity appears.
The header menu retains its existing layout with an Account settings link; #41 owns
its later identity redesign.

## Curated interest picker

Interest selection uses native independent checkboxes (`ui-interest-choice`) within
section disclosures (`ui-interest-section`). Open one starter section; search
reveals matching choices across sections. Keep all inputs in the form so collapsing
or searching never drops selections. Selected interests remain visible as quiet
Remove buttons; their names and the selection count communicate stored/pending state.
Without JavaScript, section disclosures and checkboxes remain usable.
Account settings shows saved names as informational `ui-interest-summary` chips and
an Edit interests navigation link. Suggestions are a separate optional text field.

Account access uses the same compact form/link families: email-only signup and
recovery requests lead to one neutral Check your email page; bearer setup pages
collect identity and credentials only after mail ownership. GET never mutates account
state. Required errors stay adjacent to inputs; retry/sign-in/recovery are navigation
links. Group invitations show a verification/suspension explanation in place of an
unavailable sending control.
