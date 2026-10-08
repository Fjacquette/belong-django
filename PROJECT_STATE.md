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
  waitlist, automatic notifications or reactivation in this slice.

## Activity invitations and card RSVP

- One published Activity can invite particular existing users directly and/or explicitly
  invite current active members of its associated Group. Neither expands its audience
  nor gates ordinary participation. Legacy is_personal_invitation is not used as proof.
- Group-context creation defaults group invitations on; the explicit editable choice
  is copied from Series to occurrences. Management adds/removes friends or associated
  active Group members as direct in-app invitees. No outbound activity email.
- Ordinary cards have one See details / RSVP link. Invitees have I'm coming / Can't
  make it mutations on the existing response, including beyond creator vocabulary.
  Capacity/cancellation serialization still applies. Removal/membership loss retains
  responses. Both controls stay visible; selected accent fill/white text, no checks,
  underlines or inset borders. Details retains ordinary vocabulary plus invited RSVP.
- Ordinary creator-selected vocabulary and the existing Interested default remain
  unchanged; historical records are preserved.

## Organizer announcements

- Plain-text updates belong to exactly one Activity occurrence or Group. Activity
  hosts/authorized Group organizers publish; no threads, reactions or global feed.
- In-app recipients are captured at posting: non-declined occurrence responders,
  or active Group members plus its owner. Later responders/members receive future
  updates. Reading also requires current participation/membership and context access;
  organizers can see all updates in their management context.
- Cancelled occurrences may still receive coordination updates without changing
  participation history. This slice sends no email and adds no automatic cancellation
  announcements, inbox, read receipts or notifications.

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
  seven-day group/address cooldown survives revoke/recreate. Failed sends retain quota.
- SMTP runs after commit; bounded explicit retries, no automatic loop. Existing retained
  delivery records are backfilled. Provider webhook integration is still deployment work.

## Current implementation sequence

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
- public signup must become invitation-controlled before public exposure;
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
