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
Purpose: on/off filter that may coexist with peers.
Use checkbox semantics with a consistent filter-chip visual family and obvious
selected state.
Examples: Today, Nearby, Online, Free.

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

## 7. Activity-card information hierarchy

The first one or two card bands must answer the user's first-pass decision questions
without requiring Details.

When known, these six facts belong in the top two bands:
1. activity/event name
2. organizer
3. intended audience / who it is open to
4. cost
5. time/date
6. location or Online

Recommended hierarchy:

### Band 1 — identity + immediate logistics
- activity title: dominant, max two lines
- compact secondary line: **when · where**
  - examples: `Sat Oct 10, 10 AM · Ridley Creek`
  - `Now · Online`
  - `Date TBD · Hershey, PA`

Do not spend Band 1 on a marketing headline while date/location are buried below.
A headline/summary can move lower when space is constrained.

### Band 2 — people + participation context
- organizer identity/name
- audience
- cost

Keep this compact, normally one or two metadata lines. Example:
`Janine · Friends of friends · Free`

If an organizer avatar is useful, it must not crowd out the text facts above.

Use explicit, human-readable fallbacks when information is unresolved:
- Date TBD / Anytime
- Location TBD / Online
- Cost TBD or Free/Paid where structured data supports it

Truncation may be used for density, but every truncated value must expose the full
value on hover/focus as already required by UI_PRINCIPLES.md.

## 7A. Activity-card sizing and grid behavior

Activity cards are fixed-format scanning objects, not fluid content panels. Their
visual proportions must remain stable as the result count changes.

- Define a preferred card width and a maximum card width from the existing card layout
  variables/design tokens.
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
- Filtering from many results to one or zero must not cause surrounding controls,
  Who's around, gutters, or card geometry to jump unpredictably.

A card's information density and band hierarchy are designed around this stable width;
responsive behavior should adapt columns/wrapping rather than turn the card into a
full-width banner.

## 8. Activity-card actions

Card actions are a distinct compact system, not a collection of unrelated controls.

- response choices shown directly are peer state-changing actions and use one compact
  button family/height
- current selected response must be visually obvious
- clicking the selected visible response may clear it; do not also show a tiny remove X
- if the current response is not directly shown, display the current state clearly and
  provide a coherent change/remove action
- response counts are information, never controls
- Details is navigation and uses the navigation-link family
- Hide/Unhide is a quiet private action; use the quiet-action family or an appropriate
  secondary-actions menu
- do not mix full-size pills, tiny buttons, icon-only cancellation, and pseudo-links
  arbitrarily in one footer

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
