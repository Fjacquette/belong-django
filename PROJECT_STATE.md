# Belong project state

This file is the **current-state handoff**, not the product-history archive.

For product history, philosophy, and historical user stories, use the ChatGPT Project source **Belong — Canonical Project Context**. For live implementation status, current PRs/issues and the repository are authoritative.

Keep this file short. Update it when product decisions, architecture, workflow, or implementation sequence materially change. Do not turn it into a changelog; Git history already provides that.

## Operating model

- Frank is product owner. He reacts to the running product and makes substantive product decisions.
- ChatGPT acts as technical lead/product continuity: product interpretation, architecture, issue slicing, PR review/merge, and keeping the work coherent.
- Codex is the primary implementer.
- Claude Code may be used as an independent skeptical reviewer, not as a concurrent editor.
- GitHub is the durable handoff layer. Frank should not need to copy implementation prompts/results between tools.

### Working loop

The normal loop is deliberately simple:

1. Frank reviews the running product and gives ChatGPT product feedback, criticism, or a new decision.
2. ChatGPT translates that feedback into durable GitHub issue/PR comments, acceptance criteria, sequencing, or follow-up issues as needed.
3. Frank's instruction to Codex should normally be only a short directive such as **"address PR #27"** or **"attack the next issue."**
4. Codex reads the relevant GitHub issue/PR plus the repository guidance, implements it, tests it, pushes it, and presents the exact committed browser-test preview.
5. ChatGPT reviews the resulting PR/code against the issue and product direction, writes any required corrections back to GitHub, and the cycle repeats.
6. Frank should not be used as a message bus between ChatGPT and Codex. Do not give him long implementation prompts to paste into Codex when the direction can be written to GitHub instead.

GitHub issues and PRs are therefore not merely tracking artifacts; they are the primary technical-lead-to-implementer communication channel and the durable record of active implementation intent.

Default posture: **do it now**. If product behavior needs backend/model work, build it. Complexity may require smaller vertical slices; it is not a reason to defer the behavior unless there is a concrete blocker.

## Curated interests

- Profiles select optional canonical interests from a migration-seeded catalog of
  37 activity-oriented interests across seven sections (maximum 20 selections).
- New signup prompts for interests after email verification; Save/Skip allows entry.
  Accepted invitation context survives the prompt. Existing accounts edit via settings.
- Activity and Group have optional M2M fields pointing to the same Interest records;
  ActivityCategory remains a separate broad classification. No ranking/filter changes.
- Free-text suggestions are private separate records, reviewable in Django admin;
  they never automatically become public or matching tags.

## Occurrence lifecycle and capacity

- Activity hosts and authorized associated Group organizers manage a private
  person/response roster with creator-vocabulary counts.
- Occurrences are Active or Cancelled. Cancellation stores actor/time and optional
  reason, freezes existing responses, and leaves Group, Series and siblings intact.
- Only Count me in consumes capacity. Serialized server mutations reject new
  commitments when full; interest/questions remain possible while active. No
  waitlist or reactivation. Explicit cancellation now queues opted-in participant email.

## Activity invitations and card RSVP

- One published Activity can invite particular existing users directly and/or explicitly
  invite current active members of its associated Group. Neither expands its audience
  nor gates ordinary participation. Legacy is_personal_invitation is not used as proof.
- Group-context creation defaults group invitations on; the explicit editable choice
  is copied from Series to occurrences. Management adds/removes friends or associated
  active Group members as direct in-app invitees.
  Verified organizers can also email a single existing/new recipient for a specific
  occurrence. Seven-day digest-only tokens, revocation, durable per-occurrence
  cooldowns and shared Group/Activity sender quotas use the existing mail controls.
  Matching recipient consent survives signup, login and recovery through signed
  session IDs. Audience checks precede Activity disclosure/acceptance; accepting
  adds only the direct invitation, never a response or Group membership. External
  inbox/provider delivery remains an operational pilot gate, documented in README.
- Ordinary cards navigate with See details / RSVP before responding, then a concise
  saved-state / Edit response label in Band 5. Band 4 is exclusively description.
  Interested is retired from current choices and defaults; old rows display as
  historical and are never silently converted or deleted. New Activity/Series
  defaults use Tell me more, with organizer-specific choices retained on Details.
  Invitees have I'm coming / Can't
  make it mutations on the existing response, including beyond creator vocabulary.
  Capacity/cancellation serialization still applies. Removal/membership loss retains
  responses. Both controls stay visible; selected accent fill/white text, no checks,
  underlines or inset borders. An unmatched saved response has a compact Band 5
  disclosure containing both RSVP actions and a Details/edit link. Cancelled cards
  navigate to the saved history on Details. Details retains current creator-selected
  vocabulary plus invited RSVP, including visible selection and safe removal.
- After saving a valid response (including early interest or a declined RSVP), a
  nonmember may receive a separate optional Group join offer. Open/Unlisted joins
  are active; Closed requests await normal organizer approval. Private Groups,
  owners and active/pending/blocked memberships receive no offer. Dismissal or
  acceptance is durable per person/Group; neither changes the ActivityResponse.
  Inline offers live outside cards, with shared HTMX/non-JS admission and safe
  return URLs retaining Discover context. Activity participation remains independent.

## Organizer announcements

- Plain-text updates belong to exactly one Activity occurrence or Group. Activity
  hosts/authorized Group organizers publish; no threads, reactions or global feed.
- In-app recipients are captured at posting: non-declined occurrence responders,
  or active Group members plus its owner. Later responders/members receive future
  updates. Reading also requires current participation/membership and context access;
  organizers can see all updates in their management context.
- Cancelled occurrences may still receive coordination updates without changing
  participation history. Activity updates and cancellation now create durable email
  events for verified, opted-in, non-declined responders (including historical
  responses); invitations alone and Group membership do not subscribe someone.
  Account settings controls consent, default off. Delivery snapshots never expand;
  live access, participation, sender authority and address proof are rechecked.
  Fixed notices link to authenticated canonical Details without private Activity
  text. Cancellation has priority and a separate budget; obsolete queued updates
  are suppressed. Bounded delivery retries use the management command; interrupted
  or ambiguous SMTP claims require reconciliation. Group updates remain in-app.
  #90 offers explicit global-email opt-in beside eligible saved participation on
  Details and outside Discover cards. Consent stays default off; declines, poll-only
  answers and pending enrollment do not prompt. Existing Account settings disables
  it, and notification snapshots/retries/eligibility are unchanged.
  No automatic cancellation announcement, inbox, read receipts or other channels.

## Product direction

Belong exists to reduce loneliness by helping people create and deepen relationships through things they do together.

Current durable rules:

- Activity-first. Activities are the normal discovery surface.
- Groups are useful persistent social context, but never gate ordinary activity participation.
- Support spontaneous, scheduled, open-ended, and recurring activity.
- Preserve low-friction proto-intent, but responses must communicate something useful for the specific activity.
- Activity creators choose which response options make sense for their activity; do not force one universal response vocabulary.
- Hide is a private discovery action, separate from the user's response to the organizer.
- Discussion/messaging exists for coordination, not as a content feed.
- Success is shared experiences/relationships, not engagement.
- Safety, kindness, accessibility, and opportunity remain product constraints.

## UI direction

See `UI_PRINCIPLES.md` and `DESIGN_SYSTEM.md`. The latter is the authoritative visual system for reusable control families, spacing/geometry, and card information hierarchy.

Additional current decisions:

- Less chrome, more meaning. Cooper/Tufte-style restraint is intentional.
- Group controls by the user's task, not by backend object.
- Search/discovery should help answer "what do I feel like doing?"
- Discover uses four multi-select facets: When, Where, Cost, Open to. Category remains in the data/search model without a permanent control.
- Create should be a floating **+** primary action rather than a peer navigation link.
- Friends/presence should quietly communicate "Who's around" with Active / Idle / Offline states.
- Activity cards should remain compact and rapidly scannable.
- The top one or two card bands must show the core decision facts when known: activity name, organizer, audience, cost, time/date, and location/online state.
- Truncated card text must expose the full value on hover/focus.
- Navigation is link semantics; state changes are button semantics.
- Discover's existing kebab offers enhanced Share activity: native sharing or copy
  of the canonical Details URL, with accessible feedback and a manual-copy fallback.
  Without JavaScript only Share is omitted; other menu actions remain usable.
- Mobile is a first-class layout, not desktop compressed narrower.

## Current implementation baseline

Authoritative implementation: Django, server-rendered templates + HTMX, SQLite for local dev/browser-test.

Already established:

- separate dev and persistent browser-test environments;
- baseline activity-loop tests;
- safe/idempotent demo seeding;
- visibility enforcement for Everyone / Friends / friends-of-friends;
- image upload/serving hardening;
- safe action URLs;
- rendered participation controls;
- UI simplification principles;
- automatic browser-test presentation tooling;
- cumulative discovery filters, explicit cost/GPS semantics, private Hide/Unhide;
- invitation-aware card actions, creator-selected Details responses, and floating Create;
- authenticated HTTP presence with Active / Idle / Offline thresholds.

The browser-test review environment is:

`http://127.0.0.1:8001`

For normal implementation work, Codex must present the exact committed feature HEAD there before declaring the iteration done. Frank's normal review action should be only to reload the browser.

## Beta admission (#77)

- `BELONG_BETA_MODE=true` gates all public signup completion, including old proofs
  and provisional-account recovery. Production requires an explicit true/false
  configuration; dev/test remain ordinary signup unless explicitly enabled.
- Superusers issue seven-day, email-bound, single-use codes through admin. Only keyed
  verifiers and lifecycle metadata persist; the code is shown once, never retrievable.
- Valid authorized Group/Activity email invitations explicitly grant beta admission
  with existing email proof. Source validity/authority is rechecked at completion;
  cross-browser continuation retains only the original invitation's rights.
- Admission redemption and account creation/verification are one serialized transaction.
  Abandonment or failed setup does not consume access. Existing login, recovery,
  audiences, participation, memberships and default-off mail consent remain unchanged.
  See docs/BETA_SIGNUP.md; payment work remains deferred under #87.

## Account foundation

Email-first signup/login retains stable auth.User PKs/internal usernames. #46 moves
new account creation behind 24-hour email proof: request link first, then the proven
owner chooses password, required Individual/Organization, and display name. Public
signup/recovery requests share neutral responses; unverified pre-claims can be
reclaimed only by email proof, replacing provisional credentials/identity. Recovery
proofs last one hour, invalidate old sessions and require explicit sign-in.
Invitation consent survives setup (or original-browser login after cross-browser setup). Account
settings edits identity, coarse home area, normalized square avatar, pending email
(with password confirmation), and password. Organization labels grant no privileges.
Nonempty emails are case-insensitively unique at the database level. Existing local
accounts have explicit migration/demo-only legacy compatibility in dev/test; new
user signals grant none. Missing BELONG_ENV fails closed as production. SQLite uses
IMMEDIATE transactions. Invitation sessions retain a signed ID, never a bearer
token; legacy session tokens are scrubbed. Avatars have a 25 MP decode ceiling.
No fake email backfill.
Header identity uses a transparent avatar/name disclosure and compact Account
settings / POST Logout rows. Discover remains the desktop header link and mobile
brand destination; unverified accounts retain Verify email / Logout only.

## Email abuse controls

- Only email-verified organizers send invitations; legacy/Organization status grants
  no sending bypass. Admin profile suspension blocks third-party mail without deletion.
- Fixed mail content and canonical BELONG_PUBLIC_ORIGIN prevent arbitrary message/link
  relay. Production requires HTTPS origin and provider/domain/bounce readiness (README).
- Durable hashed attempt journal + serialized reservations enforce configured signup,
  creation, self-address/IP and invitation quotas/cooldowns across retries/restarts.
  Invitations cap both 50 unique recipients and 50 attempts per rolling day, 20/action;
  seven-day Group/Activity-address cooldown survives revoke/recreate. Failed sends retain quota.
- SMTP runs after commit; Activity notifications have a durable bounded-retry outbox,
  while invitations/proofs retain explicit retries. Existing retained
  delivery records are backfilled. Provider webhook integration is still deployment work.

## Participation patterns (slices A/B and #75)

- #74 uses the reviewed [participation model](docs/PARTICIPATION_MODEL_PROPOSAL.md)
  from PR #79. Null configuration retains #60/#70 behavior and historical data.
  Version 1 remains navigation-only, including all existing slice A records.
- Version 2 enables explicitly selected Scheduled event (free/open attendance) and
  Immediate activity (free/Join now). Semantic POST actions use existing
  committed/declined responses as the single intent/capacity/notification authority:
  Going for scheduled confirmation, Joining for immediate intent. No payment or
  admission step exists; only committed intent secures a limited free place under
  the existing serialized lock. Cancellation freezes responses; removal releases
  capacity. Neither action proves observed attendance. External links never RSVP.
- Invitations request the same pattern action as ordinary participation. Scheduled
  invitees get confirmation/decline; immediate invitees get Join now, without
  universal attendance RSVPs. Audience and Group membership remain independent.
  Ordinary cards navigate to Details; invited cards show their supported actions.
- Series defaults are copied independently. Existing Activity configuration is
  immutable; no bulk conversion/history rewrite. Default creation remains the
  legacy response-choice flow/More. No universal Interested or Willing response.
  Payment processing and inquiry remain unavailable.
  #73's response-based notification eligibility/consent/history remains intact.
- #75 adds explicitly selected version 3, free three-date planning on one-off
  Activities. Yes/Maybe/No availability submissions are append-only history, separate
  from attendance. Finalization retains the Activity, configuration, options and
  answers, sets its selected date, and creates a fresh confirmation round/invitation
  for every poll participant, including all-No answers and users who lost access.
  Audience checks still gate disclosure. Ordinary nonparticipants may also RSVP.
- Only explicit round attendance (Going/declined/withdrawn history) owns these
  Activities' capacity; no vote creates ActivityResponse or reserves a place.
  Finalized dates cannot change without a reviewed new round. Existing legacy
  responses remain prior evidence; secured commitments block finalization pending
  the open reconfirmation policy. Cancellation freezes both workflows.
- Confirmation notices reuse verified-address/default-off consent, visibility,
  sender authority, fixed content, shared budgets and bounded audited retries.
  Delivery failure does not remove in-app invitations. Poll-only participation
  does not subscribe to routine updates; only current affirmative round attendance
  qualifies on these Activities. Legacy notification behavior/history is unchanged.
- #76 D1 adds explicitly selected version 4 free ongoing approval/enrollment. An
  OngoingOpportunity capability owns a separate immutable player limit/policy on its
  Activity surface; requests consume nothing. Authorized approval atomically records
  admission, enrollment and a secured limited place. Unlimited enrollment has no
  artificial place rows. Full approval leaves the request pending; denial/withdrawal
  retain history and withdrawal releases the player place. No Group join is implied.
- Organizers can publish separate linked meetings with independent audience, RSVP,
  capacity and cancellation; no people/responses/invitations are copied. Enrollment
  is not an attendance prerequisite in D1. Cancelling the ongoing opportunity freezes
  its request/enrollment evidence without cancelling meetings. Active enrollees alone
  qualify for ongoing updates/cancellation under existing email consent/access rules;
  requests and approval alone send no new mail. No Series enrollment defaults exist.
- The [#76 policy proposal](docs/RESERVATION_POLICY_PROPOSAL.md) remains the boundary
  for independent registration, payments, holds/waitlists and provider recovery. Financial
  terms/priority and later milestones need separate review/authorization; none of
  those capabilities is implemented by D1.
- #78’s spontaneous sandcastle scenario adds revocable standing permission for
  future outing invitations, separate from participation/enrollment/Group membership.
  Each fresh occurrence gets independently selected invitations and RSVPs; scope
  and channel-consent design remain open. Included in the proposal only, not implemented.

## Current implementation sequence

### Janine-first priority reset (#87)

[Issue #87](https://github.com/Fjacquette/belong-django/issues/87) supersedes the
previous implementation ordering. Prioritize real J-01–J-12 pilot walkthrough
blockers and [#68 past Activity review/clone/edit/publish](https://github.com/Fjacquette/belong-django/issues/68).
Distinguish local tests from external signup/inbox delivery and human usability
evidence. Existing D1–D3 remain functional, but payment infrastructure is deferred:
no provider sandbox experiment, payment implementation or D5 is authorized as the
next task. Beta access #77 supports pilot timing; broader follow-ups come afterward.

### Past Activities and private reuse drafts (#68)

- Account menu → Past activities & drafts lists accessible past/cancelled outings
  the user organizes. Details/list POST copying creates a private creator-owned
  ActivityDraft snapshot; no published Activity exists until explicit publication.
- Copy occurrence logistics/current defaults and manageable Group/Series associations;
  clear schedule and all invitation/response/update/cancellation/participation history.
  Group invitation opt-in starts off; current Series defaults are never reapplied.
- Native disclosed editing saves privately or validates/publishes a fresh Activity.
  Revision checks and serialized publication prevent stale overwrites/duplicate outings.
  Existing free capacity, poll/enrollment/registration authorities and data stay intact.
- Published logistics editing is outside this slice. See docs/ACTIVITY_REUSE.md for
  exact exclusions and pilot evidence gaps; payment infrastructure remains deferred.

### Discovery iteration

**#19 is complete and merged.**
Discover now uses four immediate multi-select facets: When, Where, Cost, Open to.
Selections OR within a facet and AND across facets; empty means unrestricted.
Search remains explicit. Time uses the pilot local calendar and documented Now
semantics. Physical distance buckets require browser coordinates; Online includes
Hybrid. Numeric USD cost_amount backs the dollar-sign cost tiers, preserving human
cost_display. Audience selects the exact activity audience, not viewer eligibility.
Advanced filters and permanent Category controls are removed; Show hidden is a
separate private recovery control. Repeated facet values survive pagination and
participation redirects. Existing data is preserved; only authored matching
seed-owned demo prices are populated. Cards retain organizer avatars and readable
metadata. Ordinary cards link to Details; invited cards show two complete RSVPs.
Presence reflects authenticated HTTP activity: Active within 5 minutes, Idle within
30, Offline thereafter or without a timestamp, with writes throttled to one minute.
Discover uses one Friends list in responsive panes (#40): independent scroll and a
pointer/keyboard resizable, locally remembered divider at 1024px and wider; an
Activities/Friends segmented switch below that width preserves filters, card view,
results and separate scroll positions. Pane presence is independent of matching
card counts, including zero results. Quick toggles clear their canonical dimension when turned off.
Existing demo metadata is enriched without reseeding accounts or responses.

The Groups foundation (#21) is merged. Persistent Group and GroupMembership entities are separate from legacy personal FriendGroup lists. The floating + discloses Activity (primary) and Group (secondary) creation. The settled group access modes are Open, Closed, Unlisted, and Private. Activities may link to groups but remain independently visible/participable according to their own audience rules. Owners and active organizers can issue email-bound invitations (#22); a valid invitation grants active membership directly in every access mode, including Private.

**#28 is complete and merged via PR #30.** It implements the shared control families documented in `DESIGN_SYSTEM.md`
and `assets/tailwind.css`, applied across Discover, activity cards/details, Create,
account menus, and group forms/actions. Cards use the historical portrait hierarchy:
title-only Band 1, then organizer/when/where/audience/cost in Band 2, a substantial image,
useful description and one/two fully readable activity actions. The 440px card
retains its 258px preferred/max width; 64/72px top bands and 136px overlap expose
all core metadata. Band 1 uses a restrained accessible horizontal palette gradient,
a centered medium-weight two-line title and a quiet contextual vertical kebab.
Band 2 supports three/four aligned single-line metadata rows with deliberate
logistics splitting. Full-text tooltips and noninteractive metadata tab stops
are enabled only for text actually clipped after layout, with no native tooltip duplication. Metadata and description use 13px
body text, with 16px/18px leading respectively; the description band is 128px.
Band 2 centers a fixed circular avatar against the full metadata block. Card responses
use white surfaces with accessible card-local accents against a footer matching
the title gradient. Invited RSVPs use accent fill/white text with unchanged borders and no checkmarks
or underlines; aria-pressed exposes selection. Activity forms guide
48-character titles and 40-character venue labels; legacy model storage is retained. Search, facets and
view/recovery controls share one compact wrapping toolbar. Context survives query
changes and can be cleared independently; organizer suppression is reversible and
separate from blocking/participation. The image band contains artwork only. Title
navigation opens Details for response counts, removal and external CTAs. Generic headlines stay on Details.
Known seed-owned choices and stale sample responses are reconciled without altering
real/custom/transferred data. **#22** adds organizer-issued email invitations with hashed seven-day tokens, revocation and duplicate-safe retries. A valid invitation grants active membership, including Private; acceptance consent survives signup/login and requires a matching email. Normal signup requires email; explicit acceptance can bind an unclaimed invited email to a legacy email-less account, without overwriting existing email. Wrong-account switching retains the invitation. Local delivery uses console email. **#32** clarifies access with descriptive radios, hides + in focused create flows, and adds group identity/default activity artwork using validated media assets. Group-scoped activity creation is visibly anchored and locks its group; global creation offers optional organized-group selection. Artwork defaults are copied onto new activities and may be overridden; group identity never substitutes for the human organizer portrait. **#23** adds reusable ActivitySeries defaults with optional Group and flexible/fixed cadence metadata. Creators explicitly create normal Activity occurrences with copied defaults and independent overrides; artwork precedence is Activity → Series → Group, never live inheritance. Group-series management follows active organizer authority; independent series belong to their owner. No automatic scheduler or RSVP lifecycle is added. #24 supplies roster/cancellation/capacity; #25 supplies context-only organizer updates.

### Groups / recurring activity sequence

**#20 — Janine hiking group canonical scenario**

Implementation slices are already defined and are intended to be built, not parked:

- **#21** core Group model and membership — merged
- **#22** email invitations and joining — merged via PR #31
- **#32** group creation UX + group-context activity defaults — implemented in PR #33
- **#23** recurring series and specific occurrences — implemented in PR #35 on current master
- **#24** organizer RSVP roster and occurrence lifecycle/cancellation — merged via PR #56
- **#25** activity and group announcements — in-app context updates

Key domain distinction:

- **Group** = persistent people/context
- **Series** = recurring/repeated activity pattern
- **Activity** = one specific occurrence with its own details, responses, communication, and lifecycle

## Important known follow-up areas

These are real concerns, not reasons to block the current vertical slices unless directly relevant:

- activity creation is still too large/flat and should become progressive-disclosure;
- discovery/query performance and N+1 behavior should be corrected as the UI/data set grows;
- friendship integrity constraints need strengthening before a public pilot;
- configure #77 beta admission explicitly before public exposure;
- production/Sage deployment hardening remains to be done before exposing the app publicly;
- HTMX/CDN/deployment choices should be production-hardened when production work begins.

## Source priority when something conflicts

1. Frank's latest explicit product decision
2. Current GitHub issue/PR implementing that decision
3. This file
4. `AGENTS.md` and `UI_PRINCIPLES.md`
5. Belong canonical project context
6. Current Django behavior
7. Historical implementation/design material

Do not preserve an old behavior merely because code already implements it.

## Starting a fresh ChatGPT conversation

A new conversation in the Belong Project can start with:

> Continue the Belong project. Read the Project source "Belong — Canonical Project Context", then the repository's AGENTS.md, UI_PRINCIPLES.md, and PROJECT_STATE.md, and inspect current GitHub PRs/issues. Act as technical lead and continue from the current state. Reconstruct context from those durable sources rather than asking me to repeat prior decisions.

That should be enough to resume work without carrying a giant chat forward.

## Registration eligibility (#76 D2)

- Explicit version 5 one-off Registration targets snapshot immutable USD quote,
  independent admission (open/request/invitation), allocation trigger and capacity.
  Existing attendance, poll and D1 ongoing authorities/data remain unchanged.
- Submission alone secures nothing. Eligibility-only approval allocates nothing;
  free participants separately claim under the occurrence lock. An explicit free
  request policy can secure a place atomically on approval; full keeps it pending.
- Paid quotes stop at eligibility: payment unavailable, no confirmed place, payment
  record, hold or waitlist. Series registration and policy editing are unavailable.
- Details/roster retain independent facts and history; cancellation freezes mutations.
  Only active free registrations subscribe through existing update/cancellation controls.
  See docs/RESERVATION_POLICY_PROPOSAL.md for the precise implementation boundary.

## Free reservation holds and waitlists (#76 D3)

- New capped/free eligibility-only Registration targets can explicitly add 10-minute
  holds and an optional FIFO waitlist with protected 24-hour offers. Old targets,
  ordinary RSVPs, polling and ongoing enrollment stay unchanged; no payment processing.
- Holds/offers count capacity but never confirm registration/attendance. Explicit
  acceptance replaces the exact live hold with a secured free place under the Activity
  lock. Expiry is reclaimed before allocation; retries/GET never extend deadlines.
- Queue joining/rejoining is explicit and admission-eligible; offers preserve FIFO.
  Cancellation ends unconfirmed holds/entries while retaining secured/history records.
  Capacity revisions are audited; reductions cannot evict live holds/secured places.
- Optional `expire_reservations` command records expiry/promotes proactively; POST
  cleanup guarantees capacity without a worker. Durable offer notices reuse existing
  consent/access/mail controls and do not subscribe queue participants to updates.
  See docs/RESERVATION_POLICY_PROPOSAL.md for exact boundaries.

## Payment provider feasibility (#76 D4, proposed for review)

- docs/PAYMENT_SANDBOX_DESIGN.md compares documented Stripe, Square and PayPal
  authorization/capture/void/refund, idempotency and callback/reconciliation contracts.
  Stripe manual capture with one sandbox merchant, USD and cards is the provisional
  candidate; merchant responsibility and priority/recovery decisions remain for review.
- Proposed sandbox experiments require durable capture claims, operation/inbox history,
  uncertainty quarantine, compensating refunds and bidirectional reconciliation.
  Free D1–D3 authorities/data remain unchanged; no payment code, provider account/API
  mutation, sandbox evidence or paid registration enabling is part of this iteration.
- Under [#87’s Janine-first priority reset](https://github.com/Fjacquette/belong-django/issues/87),
  D4 is a deferred documentation-only feasibility reference. No provider sandbox
  experiment, payment implementation or D5 is authorized as the next task; #68 and
  real Janine pilot walkthrough blockers take priority. Retain unresolved merchant,
  priority/refund and recovery decisions for separately reprioritized future work.

## Discover layout prototype (#92, awaiting UI judgment)

- Opt-in dev/test `/?prototype=stack` compares native-scroll moving stacks, paged
  stacks, current Stacked and Spread out with unchanged cards/query/business logic.
- The experiment reads up to 300 authorized matching real Activities and adds
  labeled inert browser-only demos to reach 64 by default. Controls stay outside
  the token/viewport-sized scrolling deck; only Paged uses set buttons.
- Optional 8/48/150/300-card simulations and delayed batches write no data;
  production defaults/ranking/pagination are unchanged. Mobile defaults to full cards
  in the experiment. Leave its PR unmerged pending human UI review.
- All four modes remain available. Experimental Regular/Tight overlap and mode
  persist in prototype-only browser storage; short stages use full-card scrolling.
  Moving keeps full foreground cards fitted at fractional positions and suppresses
  hover promotion; header-surface clicks and quiet chevron controls toggle one card with
  reachable dismissal. Deliberate browsing scroll/set changes dismiss exposure;
  resize/programmatic scroll preserve it. Covered cards retain light hue-preserving
  pastels and dark top-band text; Spread out remains unchanged.
- Comparison, geometry evidence and compromises: docs/DISCOVERY_LAYOUT_PROTOTYPE.md.
