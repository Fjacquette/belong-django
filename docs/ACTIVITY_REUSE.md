# Reusing a past Activity (#68)

Under [#87's Janine-first priority reset](https://github.com/Fjacquette/belong-django/issues/87),
this implements J-10A. Payment infrastructure remains deferred: no provider sandbox
experiment, payment implementation or D5 is the next task. PR #88 retains only
feasibility documentation; this feature does not depend on that PR merging.

## Organizer workflow

Use **Past activities & drafts** in the account menu. Search the past/cancelled
Activities that you both can see and are authorized to organize. Open Details to
review the original hike, responses and updates, or **Copy to a new draft**. The
same copy action is available on an accessible Activity's Details.

The draft belongs only to the person who copied it, including when that person is
an authorized Group co-organizer. It appears only in their draft list/editor, not
in Discover, participant Details, Group/Series occurrences, rosters or mail.

Edit the title, trailhead/instructions, date, capacity and audience. Additional
logistics, Group/Series and invitation choices, participation and artwork use native
progressive disclosures. **Save draft** retains private changes; **Publish new
activity** validates and creates a distinct active occurrence. A dated original
requires a fresh future date for a new legacy outing; Scheduled event also requires
one. Dateless patterns remain possible. Invalid/stale forms display errors; hidden
revision prevents an old tab overwriting newer edits. Publication is atomic and
replaying a publish/save after publication cannot create another Activity.

## Copy boundary

`activities/drafts.py:COPY_FIELDS` explicitly allows authored text, address/trailhead,
GPS/instructions, audience, cost/display amount, capacity, current participation
configuration/response choices, action links and image references. Interests retain
existing catalog identities. Images are referenced rather than duplicated/recreated.
Host becomes the copying organizer when they publish.

Clear start/end/posting deadline, timing prose and multiple-event marker; choose new
logistics explicitly. Do not copy responses/notes, invitations or mail-delivery records,
announcements/recipients, cancellation/actor/timestamps, hide preferences, Group-join
offers, attendance, poll answers/finalization, registration/admission/place history,
enrollments, holds/waitlist entries, ongoing meeting association or demo ownership.
Historical Interested stays on the original; a fresh draft uses current choices.

Group and Series associations carry only when currently manageable by the copier;
unmanageable associations are omitted, and the editor displays its actual selected
associations. They are optional and revalidated on save/publication. A Series must
match the selected Group (or both be ungrouped). Copy actual occurrence values;
changing/retaining a Series does not reload its current defaults or artwork. No
automatic scheduler or Group membership is created.

**Invitations start empty, including Group invitation opt-in.** The draft explicitly
explains this and exposes the off-by-default checkbox. Selecting it enables existing
in-app invitation behavior for current active members when published; audience rules
still apply. Publication itself sends no email. Organizers explicitly issue fresh
individual/email invitations through normal occurrence management afterward.

Configured patterns preserve their current contracts. A poll needs three fresh
future choices and gets a new empty poll; ongoing/registration patterns get new
independent capability/pool configuration, with no people/history and no payments.
D3 copies the current free pool capacity/policy, never its places, claims or queue.
This supports copying existing patterns without adding new pattern variants.

## Architecture and scope

An additive `ActivityDraft` table stores an allowlisted JSON snapshot, creator,
source reference/title, revision and publication identity/time. There is no published
Activity until publication, so existing audience/participation/notification code does
not need a second draft filter. No existing Activity/status/history is converted.
Publication and saving write-lock the draft before reading current state (SQLite
writer serialization; PostgreSQL row update lock). The published identity is retained
for replay recovery, even if the published Activity is later removed.

**Editing already-published Activities remains outside this slice.** Changing a
published hike's trailhead/time requires a separate reviewed logistics-update and
notification policy; use existing organizer updates for communication. Copying and
editing a new draft never changes the original hike or its Series defaults.

## Validation and pilot boundary

Regression tests cover organizer/audience authority, private draft access, explicit
copy exclusions and unchanged source/history, invalid/stale forms, Group/Series
choices, repeat publication, cancellation independence, fresh capability data,
additive migration and file-backed duplicate/save-publication races. Browser review
covers desktop/mobile and native/no-JavaScript clone/save/publish.

Local tests/fixtures do not establish #87's real-human pilot acceptance. External
signup, at least one real verification/invitation/update/cancellation inbox receipt,
SMTP canonical origin/worker readiness, and observed Janine/hiker usability remain
separate pilot evidence. This iteration sends no mail to real people and does not
claim external delivery or human acceptance.
