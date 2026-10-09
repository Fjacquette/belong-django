# Discover layout experiment (#92 / PR #94)

Review only; **leave unmerged for human UI judgment**. Open `/?prototype=stack`.
Production rejects the flag even with DEBUG enabled; normal Discover retains its
12-card pagination, card template, permissions, business logic and preferences.

## Collection and controls

The prototype renders matching authorized real Activities, up to 300, with the
existing filters and ordering. With fewer than 64 matches, JavaScript supplements
with labeled **Demo N** cards in memory. Demo numbers now match collection indices,
rather than restarting after the real cards. Copies remove forms, menus and
navigation targets before attachment and show **Demo only · no actions**. An empty
result uses an unsaved neutral source in an inert template, never a fabricated
activity link. No-JS shows only full real cards, without demos.

Filters, mode/density, progress and optional load-test controls stay outside the
scrolling results stage. Disclosures overlay it. Friends sizing and Create retain
existing behavior; gutters sit inside the pane, keeping the scrollbar at the right
browser edge. Optional real-only/8/48/150/300 collections and delayed 24-card
batches are browser simulation knobs, not product pagination or network metrics.

## Four modes and experimental density

- **Moving:** native wheel, trackpad, scrollbar and touch scroll continuously move
  covered headers. Each incoming row becomes the complete foreground, fitted
  inside the visible stage even at fractional positions. No interception or snapping.
- **Paged:** only Previous set / Next set advances the collection, by calculated
  capacity. Native wheel does not advance to another set.
- **Stacked:** the unbounded classic pile, with prototype-only pointer safeguards
  and covered-card treatment applied to the same collection.
- **Spread out:** continuous full cards. First-time mobile defaults here.

Regular exposes Bands 1+2; optional experimental Tight exposes Band 1 only.
Foreground cards keep all five bands. Existing CSS tokens determine card height C
and overlap S. Available stage H subtracts controls/context/Create clearance:
`strips = max(0, floor((H-C)/S))`; capacity is columns × (strips + one full card).
Columns follow actual results width, gutters and Friends resizing. Density/resize
recompute capacity while retaining the browsing anchor and fractional progress;
Paged re-partitions contiguous sets around its anchor. Neither changes the collection.

Click/tap non-navigation content or keyboard focus brings a card forward.
Enter/Space selects the wrapper; real links/menu/actions retain native behavior.
Pointer focus does not relocate a navigation target before activation. Focused
cards remain attached when their window scrolls away, with the retained index
reported separately. Progress includes incoming rows, not just the base window.

Covered cards retain their own palettes: title gradients mix the existing
`--card-header-left/right` colors with 12% black, keeping white title text intact.
Other bands retain their primary/secondary colors with saturation .9 and modest
brightness reduction (.97 on logistics/description; .94 on image/action).
Active, selected, focused and
intentionally hovered cards retain the original palette. No opacity reduction
causes bleed-through. Scroll clears pointer emphasis; actual subsequent mouse
movement restores it. Shared native hover/focus stacking is overridden only in
this prototype. Hover over navigation targets does not relocate them.

Mode/density persist in prototype-only browser keys `belong-prototype-card-view`
and `belong-prototype-stack-density`. Mode values retain ordinary `all`/`stacked`
terminology, but normal `belong-card-view` is never written. Explicit choices
survive resize and filter changes. If H cannot fit one full card, all overlap modes
use full-card scrolling without replacing the saved choice; it resumes when feasible.

## Browser evidence for this iteration

Chromium checked the same 64-card collection (19 real + 45 inert demos), with
reduced motion, at fractions 0, .017, .18, .503, .777, .999 and 1 in both densities.
Every full foreground/raised card stayed inside its stage. Attached indices were
unique and matched the visible range; no backend ordering/index masking was used.

| Viewport | Available H | Columns | Regular / Tight cards per column | Moving rendering |
|---|---:|---:|---:|---|
| 1440×900 | 674px | 4 | 2 / 4 | moving |
| 1024×700 | 474px | 2 | 1 / 1 | moving |
| 768×900 | 616px | 2 | 2 / 3 | moving |
| 375×812 | 434px | 1 | 1 / 1 | all |
| 1024×600 | 374px | 2 | 1 / 1 | all |

375×812 (H=434px) and 1024×600 (H=374px) cannot fit a 440px card: they use
normal full-card scrolling, retaining the requested mode. Covered incoming/outgoing
headers may clip; complete foreground cards may not. With zero extra strips, the
moving effect is successive full cards per column rather than a multi-header pile.

Native wheel checks parked the pointer on Moving and Stacked and confirmed no
successive hover activation; deliberate movement restored emphasis. Paged sets
had non-overlapping indices; Spread out exposed all 64 cards. Preferences survived
reload, search and desktop-to-mobile resize; a sentinel normal Discover preference
remained unchanged. Screenshots and state snapshots stay outside Git because they
contain local review data.

Additional browser checks passed touch selection/menu, real Details, partially
scrolled title navigation, native wheel/touch drag, no-JS real cards/Details,
empty-result safe demos, and delayed append stability through card 300. The 36
relevant Django tests and `manage.py check` passed. These checks establish mechanics
and reachability; human trackpad feel, legibility and mode preference remain the
review decision.

The focused palette correction was browser-checked side by side in Moving,
Paged and Stacked, with Regular and Tight. Exposed covered headers retained
purple, indigo, pink, green, teal and blue (at least three distinct covered palettes
in each comparison). Screenshots were inspected in both densities. Calculated
contrast from browser-resolved gradient endpoints was at least 5.12:1 for titles;
logistics contrast was at least 11.19:1 using the existing tinted-surface composite
and filter. Foreground bands had no dimming filters. Native-wheel parked-pointer
suppression and intentional hover remained functional. This iteration changes
only palette treatment and its CSS cache version, with corresponding documentation.

## Compromises and boundaries

- Covered headers translate continuously, while the complete foreground changes
  when an incoming row enters. Token sizing can leave less than one overlap strip
  of spare space, plus explicit Create clearance.
- Retained selection/focus can overlay the default foreground. Mode/collection
  changes intentionally reset comparison position; density, resize and appends
  retain the browsing anchor. First-layout timings exclude server/network.
- Demos reuse authorized card visuals/logistics with synthetic labeled titles;
  they do not establish real result diversity, query cost or ranking quality.
- Only Moving's window plus retained focus is attached; other nodes stay in memory.
  Production fetching/virtualization is not implemented by this experiment.
- No schema, production pagination/ranking, RSVP/permissions/invitations,
  notifications, beta admission or payment changes. No reseed/reset, source user
  or Activity rewrite, or original asset replacement.
