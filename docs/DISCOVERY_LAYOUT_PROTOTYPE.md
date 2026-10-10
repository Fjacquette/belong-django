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

Click/tap any visible noninteractive card area (header, photo, body or footer) to
open/close one
full card. No button, icon, chevron, glyph or visible card indicator is injected.
The title Details link, kebab and response actions remain independent.

Keyboard users focus the existing card group and press Enter/Space to toggle it.
Its accessible label announces In stack / Shown in full; off-header, screen-reader-
only instructions and a live status announce exposure/return. Descendant links,
menus and actions keep native keyboard behavior. The tradeoff is a focusable group
with explained keyboard shortcuts rather than a native disclosure button: applying
button semantics to the parent would flatten/conflict with interactive descendants,
and aria-expanded is not applied to a group. Keyboard focus alone never exposes.
No new always-visible focus/selection decoration is added to the header.

The same existing surface returns the raised card to its resting stack and
restores B/C access; selecting another card transfers exposure. HTMX response
swaps retain the group keyboard/surface behavior. Spread out remains unchanged.

Hover never changes z-order or geometry and adds no header indicator. Existing
link hover styling and the surface pointer cursor retain their native meaning. Moving and
classic Stacked dismiss exposure on deliberate wheel/touch/keyboard/scrollbar
browsing input before motion; Paged dismisses on set changes. Resize, reflow and
programmatic scroll do not dismiss it. Moving retains selected/focused nodes if
needed and reports out-of-window indices separately, without focus promotion.
Spread out and the short-stage full-card fallback do not toggle exposure.

Covered cards recede as opaque pastels: header stops mix their existing colors
with 70% white, with dark #35173c title/link/menu text. Band 2 mixes per-card
primary/secondary colors with 90% white and keeps black logistics text. These
percentages are visual tuning hypotheses, not production tokens. Footer stops use
the same 30% color / 70% white as the header; body/background stops use 5%
color / 95% white. Image-free summaries use 10% color / 90% white with dark text.
Photos/avatars retain 25% saturation and composite at 35% opacity against their
own opaque white surface. CTA text stays dark on white with pale accent borders;
saved selections retain a 20% accent / 80% white fill. Text and whole cards never
use opacity, so adjacent cards cannot bleed through.
In browse mode natural foreground cards retain the original palette. While one
card is explicitly exposed, it alone has full-color emphasis; covered cards stay
pastel. Closing restores the correct natural foreground. No wrapper opacity or
neighboring-band bleed-through is introduced.

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
successive hover activation; no pointer exposure occurs. Paged sets
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

The pastel correction was checked in Moving/Paged/Stacked × Regular/Tight,
with at least three different exposed covered palettes per comparison and six
hues overall. Side-by-side screenshots were inspected. Browser-resolved title
contrast and calculated tinted logistics contrast exceeded 4.5:1 throughout the
sampled collection. Covered titles/menu icons use dark ink; foreground bands
remain unfiltered. Native-wheel parked-pointer suppression remains; hover no
longer raises cards. The 36 relevant tests and system check passed.

The click-to-expose iteration checked A/open/close → B/open/close → C/open/close
in one column without leaving it, by mouse, touch and keyboard group activation,
across Moving/Paged/Stacked × Regular/Tight. One exposure transfers correctly,
remains fitted, survives programmatic scroll/resize and dismisses on user wheel
or set advance. Moving touch drag and keyboard PageDown also dismiss naturally
in both densities. Single-activation title Details and kebab remain independent.
A real RSVP POST in a disposable database saved with one activation and retained
exposure after its HTMX replacement; no preview participation data changed.
Spread out retains original cards/colors without exposure behavior.

The zero-header-UI correction checked surface click/tap and group Enter/Space
through A/B/C, plus independent menu/title navigation, in Moving/Paged/Stacked ×
Regular/Tight at 1440×1100, 768×1100 touch and 375×1300 touch. Header screenshots,
including long real titles and menus, were inspected. Header child structure
remains the original title zone and native menu, with no injected control/icon.
The tall narrow stage allows several headers; shorter stages retain their measured
capacity or full-card fallback. Demo surfaces toggle locally without server actions.

The whole-card correction uses existing photographic cards: Firefighter flashover
training (purple), Wednesday night paddle (green), Chill Overwatch 2 (blue), and
Stroll the Street (rose). A–D tests cover all three overlap modes and both densities
by mouse, keyboard and touch, including photo/body activation, same-card return,
underlying-header hit-testing and native menu/Details actions. Desktop also checks
the noninteractive footer gutter; touch keeps native CTA targets independent.
An isolated render of each actual card, retaining its geometry and live covered
state, allows pixel comparisons even where another card obscures it in the stack.
Covered photos gain over 40 RGB brightness points and retain under 30% of their
original chroma (mean per-pixel max RGB minus min RGB). Header/logistics/body/footer
background samples retain under 40% chroma and lighten. Selected-card interior
pixels match the original across all five bands; rounded-edge antialiasing is
excluded. Side-by-side original/covered photos and real stacked screenshots were
inspected. A real invited RSVP/pressed CTA and HTMX replacement are checked only
in a disposable database; persistent participation is untouched. These are visual
mechanics checks, not a replacement for human acceptance of the proposed tuning.

## Compromises and boundaries

- Covered headers translate continuously, while the complete foreground changes
  when an incoming row enters. Token sizing can leave less than one overlap strip
  of spare space, plus explicit Create clearance.
- Explicit exposure can overlay the natural foreground, with return available on the same header surface.
  Retained keyboard focus alone does not raise a card. Mode/collection
  changes intentionally reset comparison position; density, resize and appends
  retain the browsing anchor. First-layout timings exclude server/network.
- Demos reuse authorized card visuals/logistics with synthetic labeled titles;
  they do not establish real result diversity, query cost or ranking quality.
- Only Moving's window plus retained selection/focus is attached; other nodes stay in memory.
  Production fetching/virtualization is not implemented by this experiment.
- No schema, production pagination/ranking, RSVP/permissions/invitations,
  notifications, beta admission or payment changes. No reseed/reset, source user
  or Activity rewrite, or original asset replacement.
