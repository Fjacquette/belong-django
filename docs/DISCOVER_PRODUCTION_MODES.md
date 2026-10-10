# Production Discover presentation (#95)

Three user-selectable modes are retained for the first pilot:

- **Paged** (desktop default for new visitors): geometry-based sets of overlapping cards; use Previous/Next beside the visible range in the right-aligned Browse results pager. The foreground card is always complete. If the available pane cannot accommodate a full card, the mode uses ordinary full-card rendering instead of clipping.
- **Stacked:** familiar continuous vertical piles, with the existing behavior of bringing a card to the front on hover/focus.
- **Spread Out** (mobile default for new visitors): existing continuous full-card grid.

**Regular** stack spacing exposes Bands 1 and 2; **Tight** exposes Band 1. Both use the normal full five-band cards and their original colors, images, native title, menu and participation interactions. No explicit card-selection control or Moving mode is shipped.

The client saves the mode in the existing `belong-card-view` local-storage key, now accepting `paged`, `stacked` or `all`. Old `stacked` and `all` choices are honored. Density is saved separately in `belong-card-density`. Responsive default choices apply only when there is no saved explicit choice.

## Retrieval versus display

`activities/views.py` fetches **48 authorized, filtered results per server batch**, independent of the current viewport's visible set size. A Paged set capacity is calculated from rendered card height, stack offset, actual column count and available pane height, measured with its toolbar controls visible. Pane scroll offset cannot inflate capacity. The range reserves stable width, and the two semantic toolbar rows wrap independently within even a 320px pane. Find activities keeps search, facets and hidden recovery together; Browse results separates layout/density from the right-aligned pager. Toolbar resize and settled HTMX changes remeasure available space. Card focus survives layout repaint; entering Paged anchors around the current visible result and restores the toolbar. Its arrows move through that batch, then navigate to the next/previous server batch at the boundary. Returning to an earlier server batch uses a one-time `#discover-last-set` fragment to land at its last set. The range indicates positions across the full result count.

Stacked and Spread Out retain the standard server batch Previous/Next links. With JavaScript unavailable, the form and batch pager remain usable, and cards are ordinary full grid cards.

This 48-result batch is an **interim pilot tradeoff**, not a claim of ideal network/performance sizing. Measure decoration/query cost, especially for 48 cards and large match counts, before merging. Do not expand the batch without measurements. Separate issue #48 will address ranking and expired Activities.

## Review requirements

- Verify wide/short desktop, resized Friends pane, tablet and 320/375px.
- Verify no clipped foreground cards; visible set size changes with actual geometry.
- Verify keyboard and pointer/touch navigation through every client set, across server batch boundaries and backward into the last set of a previous batch.
- Verify old saved view modes, density changes, reload/filter persistence and mobile default.
- Verify no overlap with the existing floating Create control, card menus/RSVP, and no UI regression for Spread Out.
- Verify the 48-result query budget (N+1 concerns); run the full Django suite and actual browser tests on the exact pushed commit.
- Keep PR #94's Moving/pastel experiments out of production. Do not seed or overwrite the persistent preview database.

This is a production candidate pending tests and human browser review; it is not authorization to merge.

## Local validation and remaining query cost

The implementation review exercises 12, 30, 70 and 105 matching results using a
disposable database copy, including real existing photographs and purple, green,
blue and rose palettes. Forward and reverse traversal checks every result exactly
once across server batch boundaries in both densities, by mouse, keyboard and
touch. Wide/tall/short desktop, tablet, 320/375px, legacy/default preferences,
divider resizing, focus, no-JS batches and empty results are checked. Persistent
browser-test runs ordinary Discover at the exact pushed commit without reseeding
or replacing its data/configuration/assets. GitHub records the final preview SHA
and complete-suite results.

A measured legacy photographic fixture uses 37 SQL queries at a 12-card batch and
109 at 48 cards. In that 48-card measurement, 48 queries retrieve images and 48
additional response queries come from existing email-offer participant checks;
the response prefetch is also present. Local test-client request times were about
0.14s/0.13s respectively; these are differently warmed local observations, not a
production latency comparison or performance guarantee. The larger bounded batch
is usable locally but retains an explicit N+1 follow-up; this slice does not
change participation/email authority or build a new retrieval architecture.
