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
- $ = $11–25
- $$ = $26–50
- $$ = $51–100
- $$$ = $100+

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

### Band 1 — activity identity + primary logistics

Band 1 contains:
- the **activity/event name**
- directly beneath it, structured **when** and **where** logistics
- a visually minimal contextual `⋯` trigger in the top-right corner

#### Title layout

- title is the dominant card text, roughly 20–22px at the current card width
- allow **up to two title lines**
- use sufficient line-height/leading for descenders; title glyphs must never be clipped
  by the subtitle/logistics region
- maintain a real gap between the title line box and logistics line box; do not achieve
  density by overlapping/clipping text
- reserve a small symmetric safe inset at both left and right so the top-right menu
  trigger does not overlap or visually push the centered title off-axis

#### When/where layout

Treat when and where as **two structured atomic values**, not one arbitrary wrapping
string.

- allow up to **two logistics lines total**
- if `when · where` fits cleanly on one line, show it on one line
- if it does not fit, place **when on one line and where on the next** rather than
  allowing one value (especially location) to wrap messily across both lines
- each item should remain unbroken when it fits within the full line; only an
  individually overlong item may truncate, with its full value available on hover/focus
- do not use the generic `headline` field as a card subtitle

When and where remain the most important first-pass facts after the activity name.

#### Contextual menu trigger

The card's single contextual menu trigger lives in the **top-right of Band 1**.

- visual treatment: three white dots only; no visible pill, bordered button, or filled
  button chrome in the resting state
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

A two-color gradient/fade using the card's primary/secondary colors is encouraged
where it preserves legibility.
### Band 2 — organizer + participation context

Band 2 contains:
1. organizer
2. audience / who it is open to
3. cost

Use a two-column layout:
- left: a **fixed-size circular** organizer/profile image
- right: the two metadata text rows

The avatar's **grid cell spans both metadata rows**, but the avatar itself does not
stretch. Keep equal width and height and `border-radius: 50%`; center the circle
vertically against the combined two-row text block.

Both metadata rows share exactly the same left edge in the text column. The second
row must not tuck under the avatar or shift horizontally.

Example:
`Janine Smith`
`Friends of friends · Free`
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
- selected/committed action: filled card accent with a high-contrast text color
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

## 10. Responsive behavior

Mobile is designed, not compressed.

- no horizontal overflow at 320/375px
- primary task remains first
- controls may wrap by semantic cluster
- do not split tightly related controls across distant rows
- secondary panels/disclosures may move below primary content
- card top-band information remains visible on mobile

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

## 12. Review rule

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
