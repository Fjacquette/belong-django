# Belong — Revised User Stories and Pilot Scenarios

**Status:** Proposed product design basis, October 2026. The external Activity invitation, optional Group-join prompt, participant email notification, and reuse/clone requirements below are explicit current product-owner decisions; open design details remain marked as such.

**Source lineage:** *Friendship Engine User Stories.docx* (older, group/event-centric); *Belong user stories.docx* (concrete named people and activity-card use cases); *Belong — Canonical Project Context*; current Django product decisions, especially issues #20, #60, #70 and #74–#76. The pending participation-model proposal is [PARTICIPATION_MODEL_PROPOSAL.md](PARTICIPATION_MODEL_PROPOSAL.md); it does not implement the follow-ups. Historical examples are preserved as tests of the product model, **not** promises to implement every capability.

## 1. Purpose and governing rules

Belong helps people make and deepen friendships through things they do together. The primary discovery object is an **Activity**, understood broadly as an opportunity or proto-intent rather than only a formal scheduled event. A **Group** is optional persistent social context, a **Series** is reusable activity-pattern information, and an **Activity** is a specific opportunity/occurrence with its own audience, responses and lifecycle. An **Invitation** is a person-specific (or explicitly group-derived) relationship to an Activity, not a special Activity type.

1. **No group-first dependency:** users may discover, create, respond to and participate in an otherwise visible Activity without joining a Group. Group membership is never itself a participation gate.
2. **Low social cost:** people can help shape a plan before committing. Bobby’s poll is the initial interaction: no preliminary Interested/Willing button. No global Interested action/status/default; historical records remain readable.
3. **Meaningful participation:** #74 requires Activity participation presets, separating actions from intent, admission, places and payment. The model was reviewed in PR #79; slices A/B add configuration, genuine no-response and explicit free scheduled/immediate intent; #75 adds real date polling and independent confirmation. Null-configured #60/#70 UX remains: ordinary cards navigate with a saved-state footer, invitees get attendance RSVP, and Details retains five current creator choices with Interested excluded. Inviting someone grants neither visibility nor Group membership.
4. **Separate relations:** friendship, group membership, Activity visibility, invitation, and ActivityResponse are different facts. None silently implies another. Activity RSVPs must not silently join a Group; where the Group accepts members, offer an optional join action after a nonmember responds.
5. **Accessible, safe by design:** preserve useful privacy, reporting/blocking, suitability, and trust questions; do not assume every real-world interaction is equally low-risk.
6. **Lightweight coordination rather than a social-media feed:** announcements, updates and eventual messaging serve shared activities; avoid mandatory discussion boards, status competition or engagement farming.
7. **Open versus implemented:** scenarios below test the long-term model; Pilot 0 scope is identified explicitly. Do not read every future-story interaction as an existing endpoint.
8. **Ethical boundary:** connection is the purpose. Commercial prospecting, ideological recruitment, and exploiting users' attention are not general-purpose participation modes.

## 2. Vocabulary: human intent versus product objects

- **Activity / activity card:** an opportunity to do something; may be now, later, recurring in concept, or unspecified until interest develops.
- **Group:** optional durable collection of people with shared context, organizers and membership/access rules; useful for repeat coordination, not required to act.
- **Series:** reusable description/defaults for repeated Activities; each occurrence has independent date, response, capacity and cancellation.
- **ActivityResponse (current implementation):** one viewer’s current enum response; historical Interested is not commitment. The #74 proposal separates future intent from polls, questions, admission, capacity and payment instead of adding more combined statuses.
- **Invitation:** explicit direct Activity→User relationship, or a Group-derived invitation when the Activity explicitly invites active group members. It requests a response but does not change audience or membership.
- **Audience/visibility:** who may discover and access an Activity. Independent from invitations and Group membership.
- **Friendship:** personal relationship used for relevant social context and some invitee choices; not equivalent to Group membership or private-message permission.
- **Organizer update:** short context-specific communication, not a public discussion board.

The old *Friendship Engine* taxonomy (users, group admins, groups, events, messages, discussion boards, circles) is a useful capabilities inventory but **not** the present navigation or ontology. In particular, “Event associated with a Group” and mandatory group discussion boards are superseded.

## 3. Core user stories: Pilot 0 design basis

Each story states a human outcome, not a preferred form or database schema. “Acceptance” describes the desired end-user behavior; existing implementation should be checked independently.

### P0-01 — Create and enter Belong

**As a person invited to try Belong,** I want to establish my own account and profile, so that I can safely take part without an administrator creating my identity for me.

**Acceptance**
- A new user can follow the current email-proof signup flow, choose identity/password, and sign in; verification/eligibility restrictions are coherent and explained.
- Optional profile, interests and coarse home area are not prerequisites to finding a relevant Activity.
- An invitation accepted during signup/login can return the user to its intended context; wrong-account behavior does not leak invitation details.
- The user can correct identity/settings later.

### P0-02 — Discover something worth doing

**As someone looking for company,** I want to scan relevant Activities quickly by time, place, cost, audience and interest, so that I see possibilities without first finding a group.

**Acceptance**
- Activity cards communicate the known essentials: what, approximate when/where, organizer, cost, audience and useful suitability cues.
- Open-ended timing and unresolved plans remain legitimate; don't hide them merely because they lack a date.
- Details can be opened without mutation. Activities remain constrained by their independent visibility rules.
- Empty local networks are acknowledged without inventing matches.

### P0-03 — Create a lightweight Activity

**As someone with an idea for doing something together,** I want to publish it without excessive ceremony, so I can find out who else might be interested.

**Acceptance**
- Creating a one-off Activity does not require a Group or a Series.
- Time, place and details support “not decided yet” where appropriate.
- #74 slices A/B: the creator chooses the current response-choice flow, Scheduled/free open attendance, Immediate/free Join now, or No response required. One-off creation also offers free three-date Tentative planning (#75). D1 (#76) also offers free ongoing approval/enrollment with a separate player pool; requests do not consume places and approval secures enrollment, not meeting attendance. All seven patterns are registered, but payment and inquiry remain unavailable. D2 (#76) offers explicit registration with open/request/invitation admission, immutable quoted terms, free approval allocation or separate free claims; paid requests remain eligibility-only with payment unavailable. Scheduled confirmation/decline and immediate Join now use semantic POST actions and the existing serialized free-capacity authority, displaying Going and Joining intent respectively. Invitations use those same actions; external links never record participation. Null configuration retains five current choices and the Tell me more default; Interested is historical only. No-response configuration creates no ActivityResponse, including for invitees.
- Costs, limitations, capacity and access requirements can be conveyed when relevant. Do not make every optional field mandatory.
- The Activity can later be refined through an explicitly supported editing flow (editing scope is a follow-up where not implemented).

### P0-04 — Respond at an appropriate commitment level

**As a viewer,** I want to understand the opportunity before committing, and respond in terms meaningful to the organizer.

**Acceptance**
- Current ordinary card: “See details / RSVP” before responding, then a concise saved-state / Edit response navigation action in Band 5; Band 4 stays description-only.
- Current Details: organizer-selected committed/declined/question/more/vote choices where offered, never a selectable Interested response. A saved question/vote label is not a delivered question or stored poll answer.
- Current explicitly invited viewer: attendance RSVP on the card, including an unmatched-state disclosure, using ActivityResponse and capacity/cancellation rules. Target #74: invitations use the Activity’s participation pattern; a planning, inquiry or registration invitation must not universally force attendance RSVP. Configured invitations now request the pattern action: immediate Join now, planning poll input before finalization and fresh attendance afterward; configured no-response invitees have navigation only.
- An invitation never bypasses Activity visibility, forces a Group membership, or discards prior response history when revoked.
- A full Activity prevents new commitments but permits noncommittal responses when allowed; cancellation stops response changes and preserves history.

### P0-05 — Maintain a lightweight Group

**As a person who repeatedly brings others together,** I want an optional persistent Group so I do not have to rediscover and re-invite everyone for every activity.

**Acceptance**
- An eligible user can create a Group, give it a name/description and access policy, and administer membership.
- Group members may remain connected even when there is no scheduled Activity.
- The Group is an organizing convenience: it neither substitutes for the Activity card nor makes unrelated Activities inaccessible.
- Group members/organizers can find Group context where authorized, while ordinary activity discovery remains activity-first.

### P0-06 — Invite people to join a Group

**As a Group organizer,** I want to invite existing and new Belong users by email so that a pre-existing real-world group can move onto Belong.

**Acceptance**
- The organizer can send invitations within the existing eligibility, abuse/rate-limit and deliverability rules.
- Existing users can accept appropriately; new users can establish accounts and accept without a separate administrator workflow.
- Private/unlisted Group discovery and token handling do not expose group context to unrelated people.
- Pending, accepted, invalid/expired and revoked invitation states are intelligible.
- An invitation to **join the Group** is different from an invitation to **RSVP to a particular Activity**. An organizer must also be able to invite someone *outside Belong* to a specific Activity by entering their real-world email address; the invitation supplies an account onboarding path without requiring Group membership.

### P0-07 — Reuse a recurring plan without duplicating RSVPs

**As an organizer of repeat outings,** I want a Series of defaults and independent occurrence Activities, so each outing takes little effort but has accurate logistics.

**Acceptance**
- A Series carries reusable name/description, associated Group when relevant, cadence and other supported defaults.
- Creating an occurrence copies defaults and permits per-occurrence overrides; it does not promise automatic scheduling.
- Responses/capacity/cancellation belong to that occurrence, not the Series or Group.
- Group-context creation defaults the editable “invite active Group members” choice on; a Series copies its saved group-invite setting to occurrences.
- A Group-linked Activity does not silently invite all members unless that setting is on.

### P0-08 — Organize invitees and attendance for one occurrence

**As an Activity organizer,** I want to know who has responded to this specific outing so I can make a practical plan.

**Acceptance**
- The occurrence roster distinguishes current response states and counts committed places accurately.
- Organizer can add/remove eligible direct in-app Activity invitees and change the explicit group-invite mode; this sends no activity-invitation email in the current slice.
- An existing response survives revoking a direct invite or losing Group membership.
- When a nonmember responds to a Group-associated Activity, and that Group's current access/join rules admit new members, offer an optional, clearly separate invitation to join the Group. Do not force membership, alter their RSVP, or pretend membership is active until the Group's normal join/approval flow completes.
- Organizers cannot silently change unrelated people's response history.
- Capacity and cancellation are enforced on the server even if two people respond simultaneously.

### P0-09 — Keep people informed and cancel responsibly

**As the outing organizer,** I want to share weather/logistics changes and cancel a single outing, so responders know what has changed and I can plan the next one.

**Acceptance**
- Updates are associated with the correct Activity or Group and readable in that context by authorized recipients.
- Cancelling an occurrence preserves its identity, response history and sibling occurrences; optional reason is visible to permitted viewers.
- Activity participants must receive proactive notifications for relevant organizer updates and cancellation, **starting with email**. Delivery failures, preferences, timing and what counts as an affected participant require explicit design; posting to Details alone is insufficient.
- Delivery architecture should permit future opt-in channels (SMS/text, Discord, mobile push) without implementing them now or coupling them to the activity model.
- Cancelled Activity cards show cancellation rather than RSVP controls.

### P0-10 — Personal control and safety

**As a participant,** I want control over whom I engage with and what I reveal, so that using Belong feels safe rather than intrusive.

**Acceptance**
- Audience and invitation scope are enforced consistently in discovery, Details and actions.
- Private hiding is separate from responding and does not expose the action to organizers.
- Blocking/reporting, unwanted-contact controls and incident handling require explicit design/implementation verification before public pilot; do not claim these are complete merely because they appear in historical user stories.
- Sensitive personal data, exact whereabouts, and Group membership should never become automatically public just because two people attended the same Activity.

## 4. Janine's hiking group — the first end-to-end pilot

### Persona and success criterion

**Janine** formerly ran a hiking Group on Meetup. She already knows some hikers and sometimes organizes outings with dates, trailheads, skill expectations, weather contingencies and capacity constraints. She wants to resume organizing without rebuilding Meetup's overhead. Her members may be existing Belong users or entirely new people.

**Success means:** Janine independently creates a Belong account and a Group, invites several actual hikers, creates a reusable hiking Series and at least two independent outings, gets real per-outing responses, sends a change/update, cancels or modifies one outing, and schedules the next — all without the participants having to navigate a group-first maze.

### J-01 — Janine joins as an ordinary user

**Given** Janine does not yet have a Belong account, **when** she signs up, proves email ownership and completes required identity steps, **then** she can create and manage her own content. The product should not require a site administrator to provision her manually.

**Pilot checkpoint:** test the complete signup experience with an actual external email, including sending/receiving proof messages. A localhost console-email setup is not sufficient evidence that outsiders can onboard.

### J-02 — Janine establishes “Janine's Hiking Group”

**Given** an eligible account, **when** Janine creates a Group with a descriptive name, purpose, geographic context and suitable access policy, **then** she becomes its organizer and can find membership/invitation controls without learning backend concepts.

**Decision to validate with Janine:** Is the Group open/discoverable, closed with approval, unlisted, or invitation-only? Do not pick a universal answer for all groups. If an exact Group geography/category is needed beyond current supported fields, track it explicitly rather than assuming it exists.

### J-03 — Janine invites her former hikers

**Given** an existing list of interested hikers, **when** she invites each by email, **then** each can accept the Group invitation whether or not they already belong to Belong, subject to account verification.

**Checkpoint:** test at least one existing user, one new user and one invitation that is expired/revoked or used on the wrong account. Do not import a Meetup member list or send mass emails without consent and a clear operational plan.

### J-03A — Janine invites a non-Belong friend to a particular hike

**Given** Janine knows someone's email but that person has no Belong account, **when** she invites them to a specific Activity, **then** they receive an account-safe invitation and can sign up, view the intended visible Activity, and respond. They are not automatically invited into or enrolled in its Group. For an existing user, the same invitation should attach to their correct account.

**Checkpoint:** verify email ownership, intended-recipient binding, expiration/revocation, duplicate/rate-limited delivery, no audience bypass, and continuation after signup/login. A Group invitation is a separate operation.

### J-04 — Members arrive in useful context

**Given** a recipient follows a valid Group invitation, **when** signup/login is complete, **then** the recipient can see the intended Group context and discover its accessible Activities without being forced to complete a lengthy profile or build a friend network first.

**Checkpoint:** confirm users can understand why they were invited and what activity, if any, is coming next.

### J-05 — Janine sets up a reusable hiking Series

**Given** the Group exists, **when** Janine creates a “Weekend Hikes” Series, **then** she can store recurring defaults such as description, typical cadence, expected audience and default invitation mode without claiming that every Saturday has a fixed hike.

**Checkpoint:** an unscheduled or variable-cadence Series must be coherent; saving a Series alone must not fabricate dated occurrences.

### J-06 — Janine publishes the first specific hike

**Given** her Series, **when** she creates a Saturday hike with trailhead, start time, anticipated duration, difficulty/suitability, what to bring, weather plan and capacity where relevant, **then** a normal Activity is published with independent details and response state.

**Checkpoint:** distinguish essential logistics from optional or not-yet-final details. Trail location must not be confused with Janine's home address. Note any required fields the present creation form cannot represent without dumping everything into free text.

### J-07 — Group members and outsiders see the same Activity differently

**Given** a visible Activity explicitly inviting active Group members, **when** an active member views its card, **then** that member sees Coming/Can't make it. **When** an ordinary permitted Discover viewer sees it, **then** that viewer sees “See details / RSVP,” and the creator-selected vocabulary on Details.

**Checkpoint:** the ordinary viewer can still participate where the Activity audience allows. Leaving the Group removes group-derived direct RSVP affordance, not existing response history. A direct invitation can coexist with group-derived invitation.

### J-07A — Nonmembers are offered Group membership after RSVP

**Given** a person responds to a Group-associated hike without belonging to its Group, **when** the Group currently admits new members, **then** Belong offers an optional “Join this group” step. Declining it leaves their ActivityResponse unchanged; accepting it uses the Group's existing membership/approval workflow. No join prompt appears when that Group's policy prohibits joining.

**Checkpoint:** test open, approval-required, unlisted and private policies as appropriate; ensure neither RSVP nor direct Activity invitation silently bypasses Group admission.

### J-08 — Janine handles space and attendance

**Given** the hike has a limited number of spaces, **when** people commit concurrently, **then** only available places are consumed. **When** full, another invited member cannot commit, but can decline; existing valid choices and response history remain coherent.

**Checkpoint:** Janine can identify committed people, not merely all “interested” people. The roster should be useful for practical day-of coordination.

### J-09 — Janine sends a weather or trailhead update

**Given** a change of weather or meeting location, **when** Janine posts an Activity-specific update, **then** permitted responders can see it in that Activity and Group members do not automatically receive an unrelated global post.

**Committed pilot requirement:** send email notifications to affected activity participants for changes, organizer updates and cancellations. The current in-context announcement mechanism does not by itself satisfy this requirement. Design recipient snapshots, consent/preferences, safe delivery/retry handling and the minimum cancellation urgency semantics; leave SMS, Discord and mobile push as later channels.

### J-10 — Janine cancels one hike and schedules the next

**Given** a storm cancellation, **when** Janine cancels Saturday's hike with a reason, **then** its card/Details mark it cancelled and prior replies survive. The Group and Series remain intact; she can create a replacement/next outing from the Series without re-entering every default.

**Checkpoint:** proactive cancellation email to affected participants, response preservation, and no accidental cancellation of other occurrences. Janine must also be able to review a past hike and clone it as a draft, modify the copied details, and publish a new Activity with a new independent response history. Do not copy past RSVPs or invitations blindly.

### J-10A — Janine reuses a successful hike

**Given** a past hike, **when** Janine opens it and chooses to clone it, **then** a new editable draft has sensible copied details (including trailhead and logistics) but no prior responses or attendance. She adjusts time, meeting instructions, capacity and invitation choices, then explicitly publishes the new Activity.

**Checkpoint:** historical outing remains unchanged, drafts do not accidentally appear in Discover, and Group/Series associations and invitee defaults are deliberate.

**Implemented #68 boundary:** account menu → Past activities & drafts → Copy to a
new draft → Save draft / Publish new activity. A private creator-owned snapshot
retains occurrence logistics, clears dates and invitations, and creates the fresh
Activity only on publication. Group invitations require explicit new selection;
Series association never reapplies its current defaults. Published logistics editing
remains separate. See [ACTIVITY_REUSE.md](ACTIVITY_REUSE.md); external Janine/hiker
walkthrough and actual inbox delivery remain pilot evidence, not local-test claims.

### J-11 — Janine delegates and maintains the group

**Given** Janine needs help, **when** she authorizes another active organizer, **then** that organizer can perform only intended Group/occurrence management actions. Members can leave; Janine can handle membership requests and inappropriate participants.

**Checkpoint:** validate owner/organizer/member authority, especially which organizers may issue Activity invitations and send updates.

### J-12 — Assess whether Belong actually helped

**As Janine and her hikers,** we want a noticeably easier path from “let's hike again” to a real shared outing than Meetup provided.

**Pilot observations:** how long does setup take, how many invitees join, how many see an accessible hike, how many respond, how many show up, how often does Janine have to explain the interface, and do participants want to meet again? These are research measures, not engagement/vanity metrics.

## 5. Other named scenarios — design regression corpus

These preserve the original *Belong user stories* personas and distinct design pressures. An item marked **future** is deliberately not a Pilot 0 implementation promise.

| Scenario | Human need / acceptance pressure | Design implication | Scope |
| --- | --- | --- | --- |
| **Peter** | Join an online game immediately; up to a few others | “Now,” online joining instructions, finite capacity | Next |
| **Greg** | Bored now, flexible about what to do | Proto-intent may lack a fixed activity or location | Next |
| **Bobby** | Theme-park trip in several weeks, date TBD | Poll first → finalize → invite every poll participant to confirm → separate RSVP; votes never reserve a place (#75) | Implemented thin free three-date flow (#75) |
| **Cindy** | Find someone for a concert with unsettled plans | Shared outing, possible dates, ticket implications | Next |
| **Jan (D&D)** | Weekly game with a fixed time and player count | Reusable Series, recurring social context, specific attendance | Next |
| **Frank (sandcastles)** | Hear about future spontaneous outings, then decide each time | Revocable standing invitation opt-in → fresh outing from defaults → selected invitees → separate RSVP; no automatic attendance, enrollment or Group membership ([#78](https://github.com/Fjacquette/belong-django/issues/78)) | Design only; not implemented |
| **Jonas** | Seasonal weekend sailing companions | Repeated opportunities with variable weather and guest capacity | Next |
| **Ginger** | Party for friends and friends-of-friends | Audience expansion, invite/RSVP, hard capacity, graceful full state | Next |
| **James** | Adventurers' club with changing excursions | Group as optional organizer; varied independent Activities | Pilot-adjacent |
| **Sam** | Find an existing softball team rather than host one | Discovery of ongoing context; no forced event creation | Future |
| **Jake** | Make interests/availability discoverable without spamming friends | Persistent lightweight proto-intent, not recurring broadcast | Future |
| **Alice** | Find friends initially via low-pressure conversation | Non-dating relationship-building; messaging safety | Future |
| **Mike** | Meet neighbors after moving | Privacy-preserving local introduction, no precise home location | Future |
| **Thurston** | Retired/widowed, wants to get out and talk | Accessible low-pressure companionship, no mandatory organizer role | Future |
| **Roy** | Make friends despite social anxiety | Approachable invitations, gentle social friction, no coercive matching | Future |
| **Beverly** | Find a platonic best friend nearby | Shared-activity route to relationships, not a dating clone | Future |
| **Montgomery** | Find a theater companion | Repeated one-to-one or small-group interest | Future |
| **William** | Exercise with others, weather-sensitive | Short-notice, variable cadence, recurring interests | Future |
| **Geordi** | Find someone to take a class with | Companion for an externally organized activity | Future |
| **Kira** | Meet friends overlapping a vacation week | Temporary geography and time-window privacy | Future |
| **Lovey** | Ask friends for moving assistance | Low-pressure aid request, access/disability needs, safety | Future |
| **Hikaru** | Find help repairing storm damage | Mutual aid, skill/trust boundaries, reciprocity | Future |
| **Christine** | Offer assistance without patronizing or unsafe exposure | Safe offers of help, consent and boundaries | Future |
| **Marcia** | Seek a job through known contacts without blasting a resume | Limited-audience assistance versus commercial recruiting | Future |
| **Willy and Mary Ann** | New-parent companionship and support | Trust, privacy; childcare itself requires extra safeguards | Future |
| **Jean-Luc** | Help a shy child meet peers via parents | Adult-controlled context; minors are not Pilot 0 participants by default | Future |
| **Reginald** | Participate without pressure around his stutter | Accessibility and patient social interaction | Cross-cutting |
| **Janice** | Seek professional mentoring safely | Trust, consent, asymmetric-power protections | Future |
| **Leonard** | Offer mentoring without appearing predatory | Transparent intent and boundaries | Future |
| **Benjamin** | Share season-ticket expense | Money, eligibility, fraud safeguards; not a payment-MVP promise | Future |
| **Jadzia** | Talk with someone while feeling down | Companionship versus clinical/crisis support; strong safety design | Future |
| **Deanna** | Find a route into activism | Governance boundary: ordinary shared doing versus ideological recruitment | Policy review |
| **Carol** | Organize neighbors around a pipeline dispute | Governance boundary: organized persuasion and advocacy are not blanket-approved | Policy review |
| **Quark** | Advertise a retail sales party | Generally outside ordinary social participation; transparent commercial tools only if ever supported | Excluded pending policy |

“Next” indicates suitable candidates for future validation and slicing, **not** a committed sprint. No one scenario should force an unnecessary new object category when a simple Activity plus appropriate response semantics suffices.

### F-01 — Frank’s recurring spontaneous sandcastle outings (#78)

**Given** Frank’s standing opportunity to hear about future sandcastle trips,
**when** Alice, Bob and Carol explicitly opt in, **then** they can receive invitations
for real future outings without promising attendance at an unknown date. This is a
revocable, purpose-bound notification relationship, not ActivityResponse/Interested/
Willing, Group membership, poll participation, Series enrollment, a place or blanket
email-marketing consent. No implementation is included in this documentation PR.

**Regression scenario:** Frank creates tomorrow’s outing as a fresh Activity from
Series defaults or the approved clone flow, sets logistics and selects currently
opted-in invitees (with the ability to omit someone). Eligible recipients receive
proactive invitation notices under verified-address, visibility, channel preference/
consent, sender and delivery controls; mail failure does not manufacture attendance
or erase the independent in-app invitation. Alice goes, Bob declines and Carol does
not answer. The roster/capacity reflect only this occurrence’s actual responses.
A later trip has independent invitations, responses, capacity and cancellation.
Bob can remain opted in despite declining one outing, or revoke future invitations
without changing his prior RSVP, existing invitations or unrelated preferences.
Never select someone merely because they once attended; no Group joining is required.

**Design boundary:** candidate scope is a person-owned follow/notify relationship to
an organizer-owned standing opportunity or Series; exact target/schema, lifecycle,
organizer transfer, channel preference and notification volume remain open. Standing
opt-out must suppress unsent notices as well as future audience selection. Neither
opt-in nor invitation bypasses the new occurrence’s audience. Reuse #68/#67 foundations
where appropriate; do not turn Series defaults into mandatory subscriptions. See
[#78](https://github.com/Fjacquette/belong-django/issues/78) and
[the #74 proposal](PARTICIPATION_MODEL_PROPOSAL.md). #75 implements the thin free date-poll flow; #76 D1 provides free ongoing approval/enrollment; later policies remain design work.

## 6. Disagreements and decisions requiring explicit resolution

### 6.1 Group-first navigation — resolved

The older model prioritizes browsing Groups, joining them, then attending Events. The current model is activity-first. Groups and Series remain independently useful but optional; do not restore a mandatory Group→Event dependency.

### 6.2 Direct/group invitations versus discovery — resolved by issue #60

An invitation is a person-specific request, not an invitation-only Activity subtype or an audience grant. Current #60/#70 code asks invitees for attendance RSVP. Product direction in #74 makes the requested interaction pattern-specific; scheduled/immediate pattern actions are implemented in slice B, and planning poll/confirmation in #75. #70 retired Interested from current choices/defaults, preserving old records without conversion. #75 adds a new confirmation invitation after a poll, without treating votes as attendance.

### 6.3 Circles, boards and messaging — deferred

Older Circle objects, mandatory Group discussion boards and generalized message history are not a design mandate. Need lightweight trust, privacy and coordination; choose new social features from observed use.

### 6.4 Fee models — constrained

The old story list grants Group organizers member/event fees. Belong's later product direction rejects ordinary organizer tolls and monetization of participation/reach. Activities may disclose real costs; enabling collection, shared-cost transactions or paid institutional events requires separate product/security decisions.

### 6.5 Reuse versus automatic recurrence — resolved for now

A Series stores reusable defaults. It does not automatically schedule recurring occurrences. Any future scheduler must be explicitly requested and designed.

### 6.6 Visibility versus membership — resolved

A Group association does not itself decide who may see or answer the Activity. The Activity's own audience remains authoritative. Any future Group-only visibility mode needs explicit product/authorization design.

### 6.7 Editing, cloning and participant notifications — current product requirements

Organizers need to **view past Activities, clone one into an editable draft, modify it, and publish a new Activity**. Preserve useful logistics and defaults but create an independent Activity identity, fresh response/attendance history, and explicit invitation choices. The existing Series flow remains useful but is not a substitute for cloning a real past hike.

Organizer updates and cancellation must **push email notifications** to affected Activity participants, beyond merely displaying an announcement on Details. Provide room for later text/SMS, Discord and mobile-app push channels; only email is in the initial delivery scope. The #67/#73 baseline implements verified-email/default-off opt-in, snapshot recipients, fixed canonical notices and bounded audited delivery. External SMTP remains a pilot validation gate. #74/#75 must explicitly adapt recipients for actual polls and new confirmation invitations without fabricating ActivityResponse rows.

### 6.8 Open-ended activity lifecycle — open, issue #48

Expiration, sort order and visibility of dateless or stale Activity opportunities need explicit rules. A “sometime” proto-intent cannot be treated as an error or left at the mercy of backend NULL ordering.

### 6.9 Public-pilot privacy and abuse — open

Verify reporting, blocking, private profiles, moderation, consent, data retention, invitations and safeguards rather than treating the old feature inventory as proof of implementation. The older proposed ability for administrators to read message history is especially sensitive and must be narrowed by clear policy and authorization.

### 6.10 Janine's pilot access and external email — current requirement, open operational gate

An existing user must be able to invite a real-world email address to **a particular Activity and therefore Belong**, not merely to a Group. Invitees may already have an account or need to establish one; the incoming Activity invitation must survive onboarding and lead to the intended Activity without bypassing audience controls. Invitees must not be forced into the associated Group.

Current repository status is not proof that Janine can receive signup, Group invitation and Activity invitation emails from the intended deployment. Validate external email delivery, origin, access restrictions, response flow and account recovery end-to-end before calling the pilot ready.

### 6.11 Participation model — reviewed basis and slices A/B (#74)

Use [the reviewed model](PARTICIPATION_MODEL_PROPOSAL.md) for bounded slices. Slices A/B
add versioned configuration, No response required and free scheduled/immediate intent while keeping existing
#60/#70 behavior for null-configured Activities. Patterns are Activity configuration, not subtypes. Questions/polls/contact/
external navigation are capabilities separate from intent, approval, places and payment.
An informational Activity may require no response and must not write one for a click.
#75's poll-to-confirmation flow and #76's capacity/admission/payment policies are
referenced follow-ups, not implemented in slices A/B. #76 now has a
[capacity/admission/registration/payment policy proposal](RESERVATION_POLICY_PROPOSAL.md)
for review, comparing Janine's free capped hike, ongoing D&D approval/enrollment and
a paid 12-seat class. D1 implements only free ongoing requests/approval/enrollment, retaining distinct
admission/player place history and independent meeting RSVP. Holds, waitlists,
financial priority and refund terms remain proposed, not implemented or approved.
#76 authorizes no payment integration; the existing serialized free-event flow remains usable.
#78 adds the separately scoped standing future-invitation use case above; it does
not add an eighth participation preset or authorize implementation in this iteration.

## 7. Proposed implementation/validation sequence

**Participation sequencing:** PR #79 supplies the reviewed model; slices A/B add configuration/compatibility and explicit free scheduled/immediate intent. #75 adds a real free three-date poll, preserving the same Activity and append-only availability history through finalization. Every participant, including all-No people, receives a fresh round invitation; only explicit current-round attendance owns capacity. Prior responses remain evidence, secured legacy places block finalization, and visibility still gates invitations. Eligible confirmation email uses existing consent/abuse/retry controls; poll-only people do not subscribe to routine updates. #76 D1 adds free ongoing approval/enrollment; later #76 milestones and #78 remain separately scoped and unimplemented.

**Stage A — Janine's first real walkthrough:** external signup, Group creation, real invitations and acceptance, Series creation, first hike, invitation-based and ordinary RSVP, roster, update, cancellation, next hike. Reuse existing Django functionality; **file issues only for evidenced gaps**. Test with Janine and a few actual hikers before broadening.

**Stage B — Implement identified pilot requirements:** email-based Activity invitation/onboarding, an optional Group-join prompt after a nonmember's RSVP, reliable participant email notifications, and view/clone/edit/publish reuse of past Activities. Then simplify create flows and resolve other evidenced pilot gaps.

**Stage C — Expand proto-intent:** Bobby's time-TBD planning, Greg/Peter immediate activities, Jake persistent openness, and gentle introductions. Observe actual participation before constructing a complex relationship graph.

**Stage D — Trust-intensive cases:** aid, mentoring, minors-adjacent activities, transactions, broad stranger messaging and governance-edge scenarios receive dedicated privacy/safety/product work before launch.

## 8. Traceability and review discipline

For each future GitHub issue, reference (a) a story ID or named scenario, (b) user-visible behavior, (c) explicit exclusions, and (d) end-to-end acceptance. Do not convert historical examples into automatic commitments. When implementation diverges, record the decision in issue/PR and revise this document when it changes the durable model.

**Pilot readiness is a real human test, not merely a passing automated suite.** The initial proof is that Janine and her hikers can independently make a hike happen and then want to do it again.
