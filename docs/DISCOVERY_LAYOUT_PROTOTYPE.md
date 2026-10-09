# Discover layout experiment (#92)

Review only; **do not merge as a production layout decision**. Opt in at
`/?prototype=stack` in dev/test. Production returns 404 for this flag, even with
DEBUG enabled. Normal Discover keeps its existing layout, query and preference.
The prototype uses the same paginated query, decoration, card template, permissions
and actions. No model, migration, ranking, invitation or participation change.

## Compare

- **F: Moving stack** uses the native Activities scrollbar. Scroll past the review
  controls to see a sticky viewport window. Earlier title/logistics bands depart
  upward while later cards enter at the lower end. Covered cards can be selected
  by click/tap or keyboard focus/Enter; the selected full card comes forward.
  Hover also brings a card forward. Scrollbar dragging and Previous/Next set can
  skip directly across many results; no wheel/touch interception or motion animation.
- **A: Paged stacks** uses the same viewport-dependent geometry and conventional
  Previous/Next set buttons. It preserves scanning but requires explicit paging.
- **Current Stacked** reproduces the unbounded piles as a comparison.
- **Spread out** is the continuous full-card grid. It defaults below 640px;
  moving/paged modes also use a grid if the pane cannot fit a 440px card. No-JS
  keeps real full cards and ordinary server pagination; no simulation is loaded.

The prototype moves gutters inside the panes so the Activities scrollbar reaches
its right browser edge. Friends sizing/switching and Create retain their existing
behavior. Experiment controls reuse existing fields, radios and button families.

## Ephemeral load experiment

Choose 8, 48, 150 or 300 browser-only copies of the current page's real cards.
Titles explicitly identify simulations. All copied forms and navigational targets
are removed; simulations cannot respond, hide, share or change database records.
Real results retain their original actions. The optional batch simulation appends
24 copies every 300ms; these are test knobs, **not approved pagination parameters**.
It models delayed arrival, not provider/network/database throughput. No seed command,
fixture insertion, persisted record rewrite or asset replacement is involved.

Only the window's cards (plus focused content) are attached in F; other card objects
remain detached in memory. Spread out/Current Stacked attach the entire collection.
Appending works in this isolated layout script without changing `_card.html` or
business logic. It preserves scroll/focus and increases native scroll range. This
suggests incremental retrieval is practical, but does not implement production
fetching, cursors, temporal ordering (#48), synchronization or ranking.

## Indicative local browser results

Headless Chromium, reduced motion, local Django; timings vary by machine. Initial
page navigation/display was roughly 237–276ms. Layout-only first display after
choosing a simulation (includes cloning, excludes server/network):

| Viewport | 8 | 48 | 150 | 300 | Initial F card nodes |
|---|---:|---:|---:|---:|---:|
| 1440×1000 | 5ms | 9ms | 30ms | 69ms | 8–16 |
| 1024×900 | 4ms | 9ms | 42ms | 66ms | 6 |
| 768×1000 | 4ms | 11ms | 24ms | 62ms | 6 |
| 375×812, Spread out | 14ms | 38ms | 107ms | 227ms | all cards |
| 320×740, Spread out | 10ms | 40ms | 113ms | 201ms | all cards |

During fractional scroll an entering row temporarily adds up to one column count
of card nodes. Metrics show the live count. Checks cover keyboard selection, touch
selection/menu, no-JS Details, mode comparison, divider resize, native scrolling,
last-result reachability and delayed batches. Human wheel/trackpad comfort remains
the purpose of review; headless checks cannot establish that it feels natural.

## Known compromises / review questions

- The entire selected real page is fetched using existing pagination (12 results).
  Large sets are simulations. Detached nodes still cost memory; F bounds *attached*
  DOM rather than providing full virtualized data fetching. Production virtualization
  has not been justified by this experiment; mobile 300-card costs deserve review.
- Result order and columns use the current round-robin convention. No new stable
  cursor or #48 ranking policy is approved here.
- A focused card is retained if scrolling moves its window away; this preserves
  keyboard focus but can overlay the lower foreground until focus leaves it.
- At row boundaries a later card becomes the fully exposed foreground card. Compare
  the continuous header movement and clipped entering row on an actual trackpad;
  the interaction may still feel less natural than Spread out.
- Controls scroll away; they are deliberately review tools, not production chrome.
  Resizing changes column/window capacity while preserving native scroll offset and
  focused elements. Orientation crossings select the appropriate mobile/grid default.
- Is the lower resting position comfortable? Does bringing a header forward remain
  clear with touch? Is A simpler? Should mobile always keep Spread out? These decisions
  remain for human review before any Discover rollout or production batching.
