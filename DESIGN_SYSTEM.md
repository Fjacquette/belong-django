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

## Participation patterns (#74 slices A/B, #75 date polling)

Use [the reviewed participation model](docs/PARTICIPATION_MODEL_PROPOSAL.md).
Null configuration keeps #60/#70 controls and current creator choices. Version 1
remains navigation-only; No response required uses See details even for invitees.
The native **How will people take part?** select also offers Scheduled event
(free/open attendance) and Immediate activity (free/Join now), using version 2.
One-off Activities also offer Tentative planning (three-date poll), version 3.
One-off Activities additionally offer Ongoing activity (free, approval secures a place),
version 4. Version 5 offers one-off Registration with independent admission;
contact/payment actions are not offered.
Legacy response checkboxes are hidden for configured patterns as progressive
enhancement; their help explains that they are ignored without JavaScript.
Series defaults are copied per occurrence; existing Activity configuration stays
read-only. No automatic conversion, observed-attendance claim or Group requirement.

Band 4 stays description-only. Ordinary configured cards use **See details**, then
**Going / Edit response** or **Joining / Edit response** after explicit intent.
Invited scheduled cards use **I'm coming / Can't make it**; immediate cards use one
**Join now** button, reading **Joining** when selected. Reuse the existing compact
response family: accent fill/white selected text, unchanged borders, no checks or
underlines, `aria-pressed`, select again to clear. Immediate invitations never add
Coming/Can't make it. Cancellation retains the saved-history Details link.
Details uses comfortable POST buttons, separate validated external navigation,
visible current intent and Remove response; roster labels use Going or Joining.
Limited free capacity displays secured places, counts only affirmative intent, and
keeps declined/removal available when full. Join now is intended participation;
opening an external game is neither joining nor evidence of attendance.
Email acceptance requests the Activity's pattern action without setting intent.
Visibility and Group membership remain independent. Validate keyboard/no-JS,
filtered returns, 320/375px card geometry and capacity/cancellation races. Rich
admission/place/payment policies and standing permissions remain scoped under #76/#78.
The [#76 policy proposal](docs/RESERVATION_POLICY_PROPOSAL.md) now bounds D1
free ongoing enrollment; its remaining financial/hold/queue labels are future designs.

Planning creation shows three native future date/time fields; the finalized schedule
stays unset. Progressive enhancement hides these fields for other patterns; no-JS
help explains that they are ignored outside planning. Series do not offer dated poll
presets. Open compact cards use **Answer poll**, or **Poll answered / Edit answers**;
no availability or preliminary Willing button is an attendance mutation.
Details uses three native fieldsets with Yes/Maybe/No radios in existing comfortable
control clusters, one Save availability button, and a separate history disclosure.
Finalization happens on the organizer roster, with per-date counts and explicit
**Finalize date and invite to confirm**. The same Activity then shows its selected
date, readonly availability/history, fresh invitation copy and scheduled confirmation
controls. Keep availability, current attendance, and prior response evidence distinct.
The roster retains all submissions and attendance changes in disclosures; polls never
count as secured places. Reuse existing field/button/disclosure tokens and card bands.

D1 ongoing cards always navigate: **Request a player place**, **Request sent / View**,
**Enrolled / View**, or the retained denied/withdrawn state. Invitation does not add
attendance RSVP. Band 4 and 258×440 geometry are unchanged. Details shows the free
approval policy, separate player limit/count, actual request/enrollment state and
comfortable Request / Withdraw request / Leave ongoing enrollment POST buttons.
Past requests/decisions/enrollment/place release remain in a native history disclosure.
The organizer roster separates admission, enrollment and place facts in wrapping
rows with explicit Approve and enroll / Deny buttons. Full approval leaves Pending;
requests are neither seats nor a waitlist. Unlimited pools show No player limit.
Create a separate meeting opens a normal scheduled/free form, copying title/audience
context only (plus optional Group context), with independent date/capacity/RSVP.
Use existing field, button, disclosure and link families; no new one-off CSS. Linked
private contexts must not be disclosed to an unauthorized meeting viewer.

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
- Share activity
- divider
- Hide this activity
- Hide this organizer's activities

The first four commands keep the user in Discover and change discovery context rather
than sending them into the activity Details room. `Hide this organizer's activities`
is a private discovery preference, not a full user block.

Share activity is an enhanced `ui-context-action` button in this menu, never in
Band 5. It shares the Activity title and canonical Details URL through native Web
Share, falling back to clipboard copying with a brief `role="status"` confirmation.
If copying is denied, show a labelled read-only URL for manual copying within the
same panel. Without JavaScript, omit only Share; keep native disclosure/navigation
and Hide forms usable. Enhanced menu actions honor the `hidden` attribute.

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

Band 5 reflects this viewer's relationship to the Activity:
- ordinary discovery: one navigation link, **See details / RSVP** before responding,
  then **<concise saved response> / Edit response**;
- directly invited or explicitly invited active Group member: **I'm coming** and
  **Can't make it** RSVP buttons, using committed/declined ActivityResponse states;
- cancelled: **Cancelled** navigation to Details, with accessible saved state and
  no response mutation controls.

Invitations never expand visibility or gate ordinary participation. Title navigation
still opens Details. Creator-selected questions, votes, interest and external actions
belong on Details. Both invited labels remain visible for no response or selected
RSVP states, including without JavaScript at 320px. An unmatched creator/historical
state uses the footer disclosure described below; both RSVP choices are available
inside it, alongside a Details/edit link. A full activity disables a new commitment; its
accessible title explains Full while retaining the complete compact label.

Use one geometry: compact controls, 1px border on both peers in both states, no
checkmark, underline or inset/double border. Unselected is white with card-local
accent text/border; selected is that accent fill with white text and aria-pressed.
Use the existing contrast-safe --card-accent and neutral fallback; focus is a white
2px outline/2px offset against the shared accessible Band 1/5 gradient. Preserve
saved state in Band 5; description is never displaced by response text.

Platform utilities are secondary to the activity itself:
- Details is available through the title/card navigation pattern
- Band 1 exposes the defined contextual three-dot menu for repeated Discover-room
  operations such as related-activity exploration and hiding
- do not create additional generic utility menus elsewhere on the card merely to
  house leftover controls
- response removal, payment, questions, voting, and other richer interaction belong
  on Details
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
  in Band 5, with richer controls on Details
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
current or next Saturday/Sunday, clamping its start to today on Sunday.
No arbitrary time prose is parsed.

Physical distance buckets are [0,1), [1,3), [3,5), [5,10), [10,25), [25,infinity)
in miles. Only in-person/hybrid activities with valid coordinates match them.
Online/hybrid match Online; OR permits both modes. Geolocation denial clears only
distance choices, preserving Online and other facets with visible feedback.

`cost_amount` is an optional nonnegative exact USD amount. Paid tiers match their
labels exactly: [1,10], [11,25], [26,50], [51,100], and over 100. Decimal prices
between labelled ranges do not match a numeric tier. Paid zero is invalid in
normal model/form validation. Free uses explicit free cost type. Forms
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
- Invitation RSVP: `ui-button ui-button--compact ui-response ui-response--card`,
  two complete 12px labels, visible together without JavaScript. Card accent retains
  colors with 4.5:1 contrast against white, otherwise darkens RGB together by 10%
  steps; invalid colors use #333333. Selection changes only fill/text, keeps 1px
  border and aria-pressed, and never adds check/underline/inset decoration. Ordinary
  viewers get one navigation action using the same card palette. Details retains
  the complete creator-selected vocabulary, extended by RSVP for invitees.
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
- Band 5 owns saved response state: ordinary cards navigate using See details / RSVP
  before response, then Going / Edit response, Have a question / Edit response,
  or the corresponding concise label. Full saved state is accessible on the link.
  Historical Interested uses Past response / Edit response; Details explicitly
  labels its history without treating it as a commitment or a selectable response.
  Invited RSVPs expose pressed state. An unmatched response uses a native
  `card-response-menu` disclosure with the concise state and chevron in the footer;
  its upward panel contains full saved state, both RSVP buttons and Edit response in
  Details. The panel uses existing menu/response/link families, supports Escape and
  outside-click dismissal, and works without JS. The standard 48px footer/440px card
  remains fixed. Cancelled is a footer link to Details, with saved state in its
  accessible label. Removal stays on active Details only.
- The 128px top-aligned description band uses the same 13px body size as Band 2,
  with relaxed 18px leading and up to six lines. It contains only description, never
  saved response state or a reserved status line. External CTAs and the generic headline stay on Details.

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
The header uses `ui-identity-trigger`: transparent identity with a 44px minimum
keyboard/touch target, fixed 32px circular avatar or initials, display name (full
name/username fallback), and quiet disclosure cue. No outlined capsule. The name
truncates within available width; the accessible trigger label retains the full
identity. `ui-account-menu` is a right-aligned 176px white surface with 4px inset,
8px radius and restrained border/shadow. Account settings and POST Logout use the
same `ui-account-menu__item` family: full-width 40px rows, plain resting surfaces,
and consistent hover/focus states. No duplicated identity or navigation drawer.
Discover remains the desktop header link and the mobile Belong brand destination.
Native details/summary preserves keyboard operation; optional Escape/outside-click
dismissal restores trigger focus on Escape. Unverified accounts see
identity plus Verify email/POST Logout only; verified accounts retain Discover and
Account settings. Missing profiles are repaired with unverified defaults.

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

## Header brand

`ui-brand` is a 44px-minimum navigation target. Its `ui-brand__wordmark` uses the
canonical transparent `Purple rocket logo white on dark.png` unchanged, at 32px
high on mobile and 48px from the small breakpoint, with intrinsic proportions.
The shared favicon is the original 192px `Purple rocket 192.png`. Both assets
retain their original filenames under `static/img/brand/`.

## Occurrence management

Activity hosts and authorized Group organizers use a separate management page for
person/response rows, vocabulary-specific counts, capacity and cancellation.
`ui-roster` is a full-width, fixed-layout two-column table with semantic headings,
wrapping identity text and light row separators. Forms reuse standard fields and
secondary comfortable buttons; Create is suppressed during management.

Only Count me in consumes capacity. A full activity disables that choice for
people without a commitment, labels it Full, and keeps interest/questions available.
Existing commitments can be withdrawn while active. The server serializes response
changes and cancellation on the occurrence before checking remaining places.
Cancelled cards prefix the title with Cancelled in Band 1 and replace Band 5's
response controls with a Cancelled link; its accessible label identifies saved state. Details
and management show the optional reason. No controls appear in the image band.
Cancellation freezes responses, retaining their identities/states/timestamps, and
does not alter sibling occurrences, Group or Series. No waitlist, reactivation or
notification workflow is introduced.

## Organizer updates

### Reusing an outing (#68)

The account menu adds **Past activities & drafts** using its existing navigation-row
family. The private list uses wrapping Details links, semantic dates, a native search
form and comfortable **Copy to a new draft** POST buttons. Organizer Details offers
the same copy action outside the card bands.

The focused draft editor suppresses Create. Title/description, new schedule,
trailhead/instructions, capacity and audience are directly visible. Group/Series and
invitation choices, participation, extra logistics/cost and artwork use native
`ui-disclosure` sections and existing field families; erroneous sections open.
Private state and cleared invitations are explicit. **Save draft** is a secondary
comfortable action; **Publish new activity** is primary. No JavaScript is required;
optional existing participation enhancement hides irrelevant pattern fields.
No new CSS/control family or card geometry is introduced.

Updates live on Activity Details/management or Group Details, never on Discover
cards. Reuse section headings, `ui-link` navigation to a focused compose form,
`ui-field` plain-text textarea and comfortable primary Post update button. Each
update shows author identity, semantic timestamp and escaped wrapping text. Lists
show 20 updates per page with Newer/Older navigation; no feed controls or reactions.
The compose form names its context and audience and suppresses floating Create.

## Activity invitations

An Activity is the published occurrence; invitations are per-viewer relationships,
not an Activity subtype or the legacy personal-invitation boolean. Organizers use
occurrence management to toggle inviting current active associated Group members
and add/remove direct invitees from their friends or that Group's active membership.
These POST/CSRF forms reuse standard fields, checkbox, and comfortable action families.
Group-context creation defaults the explicit group-invite choice on; Series copies
that choice into occurrences. Loss/removal changes affordances, never response history.
Organizer-selected current vocabulary remains Activity-specific. Interested is
retired from creator choices, participant mutations and new Activity/Series defaults.
Tell me more is the noncommittal creation default; organizers may choose the other
current options instead. Historical Interested rows and authored JSON remain stored;
Details/rosters identify the historical state, while active choices exclude it.

Occurrence management has a separate single-address **Invite by email** form using
the same `ui-field`, comfortable button and inline error families. It lists address
and delivery-invitation state with a POST Revoke action, never bearer links/digests.
Unverified/suspended organizers and cancelled Activities show the relevant reason
instead of a send form. Incoming Activity invitation pages reuse focused account
forms/links and suppress floating Create. Show Activity title/description only after
matching-account verification and audience checks; anonymous/wrong-account or denied
viewers get a context-free sign-in/signup/access explanation. Acceptance leads to
Details/RSVP without an automatic response or Group join. Group invitations remain
a distinct operation.

## Optional Group join after responding

A successful Activity response may reveal a quiet inline **Also join this Group?**
section. On Details it follows participation; on Discover it sits between filters
and results, outside card bands. A hidden empty live region reserves no layout space.
HTMX replaces that region separately from participation, without navigation, a modal
or moving keyboard focus; ordinary POST redirects retain the same return context.
Card Details links carry that Discover return, validated on Details; canonical
Share URLs remain free of personal filters or query state.
Use the existing heading/link, `ui-cluster`, secondary and quiet comfortable button
families. Name the saved Activity and eligible Group, make joining explicitly optional,
and explain approval for Closed Groups. **Join Group** / **Request to join** and
**Not now** are POST actions; the Group name and completion’s **View Group** are links.
No member list appears. Dismissal persists per person/Group across sessions and
occurrences, so later response changes do not repeatedly ask. Joining/dismissing
does not change the response or close Activity participation.

## Registration eligibility (#76 D2)

Registration cards navigate with View registration or concise saved state / View;
full current state remains in the accessible link label. Band 3/4 and fixed card
geometry remain unchanged. Details uses existing heading/field/button/disclosure
families: immutable quote and admission/allocation terms, separate admission/place/
payment facts, Agree to terms and submit registration, Claim free place when eligible,
and Withdraw registration. History uses native disclosure. Paid quotes explain payment
unavailability without a checkout control or confirmation promise. Roster uses wrapping
rows and explicit Approve eligibility / Approve and secure free place / Deny request.
Creator admission/allocation selects appear only for Registration with JS; no-JS help
states their scope and other patterns ignore them. Series has no registration controls.

## Free reservation holds and optional waitlist (#76 D3)

Only capped/free eligibility-only Registration creation offers the explicitly selected
hold/waitlist variant. Reuse native checkbox, field and comfortable button families;
non-registration forms ignore these fields. Details distinguishes secured places from
held/offered counts and shows absolute semantic `time` deadlines and no-renewal terms.
Reserve free place / Confirm free registration / Release / Join or Leave waitlist /
Check availability are POST buttons. Reads show Expired without renewing or mutating.
History uses native disclosure. Roster separates admission, secured places, holds and
FIFO entries, with a versioned capacity form that cannot evict places. Cards navigate
with Place held / Place offered / Waitlisted / Offer expired state; no timer, mutation
or badge in the image/description bands, and no change to fixed card geometry.


### Contextual Activity email consent (#90)

Details shows a compact global-email opt-in beside eligible saved participation.
Discover uses one secondary prompt outside the card bands, updated out of band
following card RSVP. Copy states that Activity update/cancellation email consent
applies to all Activities the user participates in; a comfortable secondary POST
button enables it. Account settings remains the opt-out destination. No checkbox
is preselected, and no participation action enables consent. Reuse `text-sm`,
`space-y-2`, `ui-link` and existing secondary controls; native POST works without
JavaScript. Declines, poll votes alone, pending enrollment and cancelled Activities
do not offer participant notices; enabled accounts are not prompted again.


### Invitation-only beta signup (#77)

Reuse the existing focused signup/setup cards, `ui-field` inputs and comfortable
primary submit buttons. Signup explains invitation-only beta in one short paragraph;
ordinary admission uses a password-style code field that never echoes submissions.
A valid Group/Activity email invitation explains that no separate code is needed.
Setup only asks for a code if its emailed proof lacks valid admission; it always
requires the existing email proof, identity and password fields. Native POST/CSRF
works without JavaScript. Generic credential errors reveal no account, issuer or
private Activity metadata. Code administration uses existing Django admin controls.

### Isolated Discover layout prototype (#92)

`/?prototype=stack` remains dev/test-only, unmerged pending UI judgment. Its compact
segmented comparison strip and native Filters/Prototype disclosures stay outside an
independently scrolling card viewport; panels overlay rather than consuming deck
height. Card dimensions/top-band offsets come from existing design variables, and
viewport height/width determine capacity. Only Paged has explicit set buttons;
Moving uses continuous native scroll without interception/snapping. Gutters sit
inside the pane so its scrollbar meets the browser edge. Default browser-only Demo
supplements are clearly labeled, have no actions, and never write data. Normal
Discover is unchanged. See docs/DISCOVERY_LAYOUT_PROTOTYPE.md for state snapshots,
selection/focus behavior, mobile full-grid fallback and review compromises.

Within this experiment only, Regular overlap exposes Bands 1+2; optional Tight
exposes Band 1. Both use existing band tokens and keep every foreground card's
five bands intact. Moving pins the current full foreground within the visible
stage while covered headers continue translating at fractional scroll positions.
Covered titles use opaque pastels from each header gradient stop (30% original
color / 70% white), with dark belong-purpleDark title/link/menu ink. Covered
logistics use a lighter coordinating primary/secondary tint (10% color / 90%
white). These are prototype tuning values, not approved production tokens.
Covered footer stops use the same 30% color / 70% white as the header.
Body/background stops use 5% color / 95% white; image-free summaries use 10%
color / 90% white. Photos and avatars retain 25% saturation and composite at
35% opacity against their own opaque white surface. Text is never faded. Covered
CTA text is dark on white, with pale accent borders; a saved selection retains a
20% accent / 80% white fill. No whole-card opacity or neighbour bleed-through.
In browse mode the natural foreground retains its original palette. While a card
is explicitly exposed, only that card has full-color emphasis; closing restores
the natural foreground. Hover/focus alone never raises or expands cards.
Any visible noninteractive card surface toggles exposure: no injected
button, icon, chevron, glyph or other visible card indicator. The existing card
is a focusable group, with Enter/Space handling only on the group itself; its title
link, menu and actions retain their own semantics. Off-header screen-reader-only
instructions and a status announcement describe exposure/return. A group is used
instead of a button role to avoid flattening/nesting its interactive descendants.
The same card surface stays reachable to return the raised card to the stack.
Deliberate browse scrolling dismisses exposure;
programmatic scroll and resize do not. Paged set changes dismiss it too.
Prototype-local mode/density preferences never write normal Discover's preference.
