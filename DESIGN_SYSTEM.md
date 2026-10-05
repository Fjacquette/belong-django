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

### Discovery dimension selector
Purpose: choose one value from a compact multi-valued discovery dimension.
Use native select/combobox semantics and the standard field/control geometry.
Changing a discovery dimension applies immediately; free-text search remains
explicit and submits only on Search/Enter.

Current visible discovery dimensions:
- **When:** Any time / Now / Today / Tomorrow / This week / This weekend / Open-ended
- **Where:** Anywhere / Near me (25 mi) / Online / In person. Keep this a single flat
  selector; do not reveal a second radius control. The 25-mile pilot radius is the
  current Nearby behavior. Hybrid activities may match both Online and In person
  because both participation modes are available. Near me should include in-person
  or hybrid activities with usable coordinates inside 25 miles.
- **Cost:** Any / Free / Paid / Unknown
- **Open to:** Any / Everyone / Friends only / Friends of friends

Free-text search answers the primary **what** question. Category remains part of the
data/search model but is not a permanently visible discovery selector by default.
If category browsing later proves important, surface it contextually rather than
adding another always-visible control.

These are canonical dimensions. Do not duplicate the same state elsewhere.

The current product does **not** need an Advanced filters panel once these selectors
exist. Remove it rather than preserving an empty abstraction.

Hidden activities are not a discovery dimension; they are private list-management
state. Give them a separate quiet recovery control such as `Show hidden` / `Hidden
activities`, visually and semantically distinct from the discovery selectors.
Future genuinely advanced search capabilities (for example custom date ranges) may
justify a new secondary control later, but do not keep an Advanced filters panel in
anticipation of hypothetical features.

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
- directly beneath it, a compact **when · where** subheader

When and where are the most important first-pass facts after the activity name.
This deliberately follows the strongest historical Belong prototypes.

Examples:
`Sat Oct 10, 10 AM · Ridley Creek`
`Now · Online`
`Date TBD · Hershey, PA`

Do not use the generic `headline` field as a card subtitle. It may remain in the
data model/details, but it is not entitled to scarce card space.

The title may navigate to Details, but it should retain title typography rather
than permanent underlined-link styling.

A two-color gradient/fade using the card's primary/secondary colors is an
encouraged Belong treatment where it works visually.

### Band 2 — organizer + participation context

Band 2 contains the remaining high-value decision information:
1. organizer
2. audience / who it is open to
3. cost

Two compact readable lines are usually sufficient, for example:
`Organized by Janine Smith`
`Friends of friends · Free`

The organizer/profile image is part of the social identity of the activity and should
remain in Band 2 when available. Use the compact avatar treatment from the original
Belong cards and design the metadata lines around it. Do not remove the organizer
image merely to make a poor metadata layout fit; instead shorten/rebalance metadata
presentation while keeping the core facts readable.

Core decision facts must be understandable without hover/focus. Shorten presentation,
rebalance lines, or remove decoration before truncating essential meaning.

Use explicit unresolved states such as Date TBD, Location TBD, Online, Cost TBD.

### Band 3 — image

The image remains a major visual element and should not be cannibalized to make room
for controls. Preserve roughly the original/prototype visual prominence.

Artwork uses `object-cover`, so some cropping is inherent. Do not shrink the image
viewport so far that normal subject matter is routinely cut off.

### Band 4 — useful description

Band 4 should have enough height for several useful lines of description.

- Prefer roughly 4–6 readable lines at standard card size.
- Do not spend this band on a generic subtitle/headline.
- Optional external/context link(s) may appear here only when they materially help
  understand the activity; do not crowd the description with platform controls.

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
- stateful response actions expose selected state
- external/action links rendered as primary activity actions may use the same
  footprint but must expose their navigation/external semantics appropriately
- do not place Details, Hide/Unhide, generic Actions, response counts, or other
  platform utility controls in the take-action band
- if the activity has more than two possible responses/actions, choose the one or
  two most useful direct actions and expose the rest on Details

Platform utilities are secondary to the activity itself:
- Details is available through the title/card navigation pattern and/or another
  clearly separated navigation affordance outside Band 5
- Hide/Unhide and other private/infrequent platform actions belong in a secondary
  card utility/menu outside Band 5
- response counts are information, not actions

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
- secondary card utilities use one consistent secondary-actions pattern outside the
  take-action band
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
