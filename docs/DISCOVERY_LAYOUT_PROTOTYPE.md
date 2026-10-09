# Discover layout experiment (#92 / PR #94)

Review only; **leave unmerged for human UI judgment**. Open `/?prototype=stack` in
dev/test and scroll over the cards immediately. No simulation selection or paging
is needed. Production rejects the flag, even with DEBUG enabled; normal Discover
still uses its existing 12-card pagination, templates, permissions and preference.

## Default collection and controls

The experimental view renders all matching, authorized real Activities up to a
300-record safety limit, preserving the current filters, ordering, decoration and
card template. The ordinary server page links are absent in the prototype. When
fewer than 64 match, JavaScript supplements with distinguishable **Demo N** cards
in browser memory. Real cards retain Details, menus and participation actions.
Demo copies remove forms, navigational targets and menus before attachment, and
show **Demo only · no actions**. With zero matches, the source is an unsaved neutral
card in an inert HTML template; no fabricated target becomes actionable.

Filters, comparison controls and range remain **outside** the deck's scroll area.
Filters opens the existing search/facet form; Prototype opens optional load-test
settings, counts, timings and Exit. Neither disclosure changes deck height when
opened. A simple visible range communicates progress; only Paged has set buttons.
Friends sizing/switching and Create retain their existing behavior. The deck's
scrollbar reaches the right browser edge, with gutters inside its content.
No-JS renders the real collection as full cards (up to 300); it adds no demos.

## Interaction and geometry

- **Moving (F):** native wheel, trackpad, scrollbar and touch drag continuously
  translate the exposed headers and entering foreground row. There is no Next set
  control, wheel interception, snapping or automatic animation. Scroll directly to
  any position; previously unseen cards enter without changing pages.
- **Paged (A):** native wheel does not advance its collection. Explicit arrow
  buttons (Previous set / Next set) advance by the geometry-derived set capacity.
- **Stacked:** the current unbounded pile, on the same collection, for comparison.
- **Spread out:** ordinary continuous full cards, default below 640px. If the actual
  viewport cannot fit one full card, Moving/Paged also fall back to a full-card grid.

Read card dimensions and combined top-band height from the existing CSS design
variables, rather than hard-coding a 12-card layout unit or card pixel constants.
After fixed controls/context and Create clearance, let H be the actual scrolling
viewport's available height, C the card height, and S the combined top-band height.
Exposed strips per column = `max(0, floor((H-C)/S))`; set capacity = column count ×
(strips + one full card). Column count follows the results width after Friends
resizing and the actual scrollbar/gutters. The final native scroll position lands
on the final result window, without a trailing empty result page.

Click/tap non-navigation content or focus a card to bring it forward. Keyboard
Enter/Space on the card selects it; real title/Details/actions retain their native
behavior. Selected/focused content fits within the visible stage; pointer focus
alone does not move a navigation target before its click completes. Focused cards
remain attached if their window scrolls away. Resizing preserves the browsing
anchor; delayed appends retain existing nodes and native scroll offset.

## Evidence: one unchanged default collection, 0% / 50% / 100%

Headless Chromium, reduced motion; same 64-card collection across all viewports:
19 authorized real matches + 45 in-memory demos in the local review environment.
No source records or assets were changed. Screenshots were inspected at each of
these positions; state snapshots below make the comparison reproducible without
committing local user data/images. Counts vary if matching records or filters change.

| Viewport | Available H | Columns × cards/column | Scroll 0% | Scroll 50% | Scroll 100% | Paged Next set |
|---|---:|---:|---|---|---|---|
| 1440×1000 | 774px | 4 × 3 | 1–12 (0px) | 25–36 (884px) | 53–64 (1768px) | 13–24 |
| 1024×700 | 474px | 2 × 1 | 1–2 (0px) | 31–32 (2108px) | 63–64 (4216px) | 3–4 |
| 768×900 | 616px | 2 × 2 | 1–4 (0px) | 31–34 (2040px) | 61–64 (4080px) | 5–8 |

A native 17px wheel increment changed header/card positions by 17px without moving
controls. After eight additional 25px increments, each view had advanced one result
row (first card 1 → 5 desktop, 1 → 3 short desktop/tablet). Paged wheel input kept
its initial set and scroll offset zero; its Next button produced the sets above.
Friends resizing changed columns 4 → 3 on desktop and 2 → 1 on short desktop,
while the scrollbar remained at the right edge. The 375×812 and 320×740 views used
single-column Spread out with all 64 cards reachable through native scrolling.

Browser checks also cover keyboard selection, touch selection and real menus,
real Details, a partially scrolled title's direct navigation, native wheel/touch
drag, no-JS full real collection/Details, empty-query-result safe demos, and delayed
append stability through card 300. Demo forms/navigation targets are absent.
These checks demonstrate mechanics and reachability, **not proof of usability**.
Human trackpad feel, legibility and preference remain the review decision.

## Optional load experiment and compromises

Prototype's collection settings offer real-only and 8/48/150/300 fully simulated
sets. Delayed 24-card / 300ms batches are test knobs, not product decisions or
measurements of network/query throughput. Default collection construction/layout
was roughly 10–14ms for the three wide views and 36–51ms on narrow full grids in
this local run; timings exclude server/network and do not establish user experience.

- Appending does not require changes to `_card.html` or business logic. Only the
  moving window plus focus is attached; other card nodes remain in memory. Production
  fetching/virtualization is not implemented or justified by this bounded experiment.
- Between row boundaries an entering card is partially clipped; selecting/focusing
  it reveals the full card. At the short height no extra header strip fits, so the
  effect is sliding single cards per column rather than a multi-header pile.
- Token sizing can leave less than one top-band strip of spare vertical space,
  in addition to the explicit Create clearance. It does not grow with result count.
- Retained keyboard focus may overlay the foreground until focus leaves. Choosing
  a new mode/collection resets its comparison position intentionally; native scroll
  and batch arrival do not reset it. Resizing can change the window capacity.
- Demos reuse authorized cards' visual/logistics content with labeled synthetic
  titles. They do not prove real-world result diversity, query cost or ranking.
- No schema, production pagination, ranking (#48), permissions, RSVP/invitation/
  notification, beta admission or payment changes. No seed/reseed/reset, persisted
  Activity/user rewrite, or original asset replacement.
