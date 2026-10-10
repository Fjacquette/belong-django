# Production Discover presentation (#95)

Three user-selectable modes are retained for the first pilot:

- **Paged** (desktop default for new visitors): geometry-based sets of overlapping cards; use the unobtrusive Previous/Next set arrows beside the layout selector. The foreground card is always complete. If the available pane cannot accommodate a full card, the mode uses ordinary full-card rendering instead of clipping.
- **Stacked:** familiar continuous vertical piles, with the existing behavior of bringing a card to the front on hover/focus.
- **Spread Out** (mobile default for new visitors): existing continuous full-card grid.

**Regular** stack spacing exposes Bands 1 and 2; **Tight** exposes Band 1. Both use the normal full five-band cards and their original colors, images, native title, menu and participation interactions. No explicit card-selection control or Moving mode is shipped.

The client saves the mode in the existing `belong-card-view` local-storage key, now accepting `paged`, `stacked` or `all`. Old `stacked` and `all` choices are honored. Density is saved separately in `belong-card-density`. Responsive default choices apply only when there is no saved explicit choice.

## Retrieval versus display

`activities/views.py` fetches **48 authorized, filtered results per server batch**, independent of the current viewport's visible set size. A Paged set capacity is calculated from rendered card height, stack offset, actual column count and available pane height. Its arrows move through that batch, then navigate to the next/previous server batch at the boundary. Returning to an earlier server batch uses a one-time `#discover-last-set` fragment to land at its last set. The range indicates positions across the full result count.

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
