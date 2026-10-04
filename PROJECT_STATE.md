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

See `UI_PRINCIPLES.md`.

Additional current decisions:

- Less chrome, more meaning. Cooper/Tufte-style restraint is intentional.
- Group controls by the user's task, not by backend object.
- Search/discovery should help answer "what do I feel like doing?"
- Discover owns filtering; Categories is a filter dimension, not a competing primary destination.
- Quick discovery filters should include Today, Nearby, Online, and Free with real pilot-grade backend support.
- Create should be a floating **+** primary action rather than a peer navigation link.
- Friends/presence should quietly communicate "Who's around" with Active / Idle / Offline states.
- Activity cards should remain compact and rapidly scannable.
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
- creator-selected direct intent controls, compact cards, and floating Create;
- authenticated HTTP presence with Active / Idle / Offline thresholds.

The browser-test review environment is:

`http://127.0.0.1:8001`

For normal implementation work, Codex must present the exact committed feature HEAD there before declaring the iteration done. Frank's normal review action should be only to reload the browser.

## Current implementation sequence

### Discovery iteration

**#19 is complete and merged.**
Today uses America/New_York; Nearby requires browser location within 25 miles;
Online includes Hybrid; Free requires explicit free cost. Advanced filters retain
query state across pages; quick shortcuts share canonical advanced dimensions.
Text search submits only on Search or Enter in its own cluster. Advanced filters is
collapsed until opened; the explicit Stacked / Spread out selector on the results utility line changes only local view state. Hide is private
and reversible. New activities default only to Interested; creators explicitly add
stronger/context-specific responses. Existing choices/order are preserved. Cards expose
the first two creator-selected responses; Details exposes all, and repeating a selection clears it.
Presence reflects authenticated HTTP activity: Active within 5 minutes, Idle within
30, Offline thereafter or without a timestamp, with writes throttled to one minute.
Who’s around uses width-based page layout independent of matching card counts,
including zero results. Quick toggles clear their canonical dimension when turned off.
Existing demo metadata is enriched without reseeding accounts or responses.

The Groups foundation (#21) adds persistent Group and GroupMembership entities,
separate from legacy personal FriendGroup lists. The floating + discloses Activity
(primary) and Group (secondary) creation. Groups have public/unlisted/private
visibility and open/approval/invitation-only join policies. Membership rosters are
visible to active members; organizers approve requests and the owner appoints additional
organizers. Activities optionally link to a group their creator organizes; group
membership never gates ordinary activity participation. Email invitations are #22.
GitHub remains authoritative for merge status; #22 is the next implementation slice.

**#28 — Establish and apply a coherent Belong UI design language** is an explicit follow-up for visual/spacing/control consistency. It should inform new UI work, including Groups, but is not a reason to block the current functional slices.

### Groups / recurring activity sequence

**#20 — Janine hiking group canonical scenario**

Implementation slices are already defined and are intended to be built, not parked:

- **#21** core Group model and membership implemented in this iteration
- **#22** email invitations and joining
- **#23** recurring series and specific occurrences
- **#24** organizer RSVP roster and occurrence lifecycle/cancellation
- **#25** activity and group announcements

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
