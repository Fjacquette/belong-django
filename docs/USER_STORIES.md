# Belong — Revised User Stories and Pilot Scenarios

**Status:** Proposed product design basis, October 2026. Review with product owner before treating unresolved choices as commitments.

**Source lineage:** *Friendship Engine User Stories.docx* (older, group/event-centric); *Belong user stories.docx* (concrete named people and activity-card use cases); *Belong — Canonical Project Context*; current Django product decisions, especially issues #20 and #60. Historical examples are preserved as tests of the product model, **not** promises to implement every capability.

## 1. Purpose and governing rules

Belong helps people make and deepen friendships through things they do together. The primary discovery object is an **Activity**, understood broadly as an opportunity or proto-intent rather than only a formal scheduled event. A **Group** is optional persistent social context, a **Series** is reusable activity-pattern information, and an **Activity** is a specific opportunity/occurrence with its own audience, responses and lifecycle. An **Invitation** is a person-specific (or explicitly group-derived) relationship to an Activity, not a special Activity type.

1. **No group-first dependency:** users may discover, create, respond to and participate in an otherwise visible Activity without joining a Group. Group membership is never itself a participation gate.
2. **Low social cost:** a person may express interest before choosing date, venue, companions or precise plan. Do not force an RSVP when tentative interest is the actual question.
3. **Different degrees of commitment:** ordinary Discover cards navigate to Details/RSVP; invited viewers get direct Coming/Can't make it responses, subject to capacity/cancellation. Details retains organizer-selected response vocabulary, including Interested. Inviting someone does not grant visibility.
4. **Separate relations:** friendship, group membership, Activity visibility, invitation, and ActivityResponse are different facts. None silently implies another.
5. **Accessible, safe by design:** preserve useful privacy, reporting/blocking, suitability, and trust questions; do not assume every real-world interaction is equally low-risk.
6. **Lightweight coordination rather than a social-media feed:** announcements, updates and eventual messaging serve shared activities; avoid mandatory discussion boards, status competition or engagement farming.
7. **Open versus implemented:** scenarios below test the long-term model; Pilot 0 scope is identified explicitly. Do not read every future-story interaction as an existing endpoint.
8. **Ethical boundary:** connection is the purpose. Commercial prospecting, ideological recruitment, and exploiting users' attention are not general-purpose participation modes.

## 2. Vocabulary: human intent versus product objects

- **Activity / activity card:** an opportunity to do something; may be now, later, recurring in concept, or unspecified until interest develops.
- **Group:** optional durable collection of people with shared context, organizers and membership/access rules; useful for repeat coordination, not required to act.
- **Series:** reusable description/defaults for repeated Activities; each occurrence has independent date, response, capacity and cancellation.
- **ActivityResponse:** one viewer's current participation response to an Activity; interest is distinct from commitment.
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
- The author chooses the ordinary response vocabulary; the default remains **Interested**, not a universal commitment.
- Costs, limitations, capacity and access requirements can be conveyed when relevant. Do not make every optional field mandatory.
- The Activity can later be refined through an explicitly supported editing flow (editing scope is a follow-up where not implemented).

### P0-04 — Respond at an appropriate commitment level

**As a viewer,** I want to understand the opportunity before committing, and respond in terms meaningful to the organizer.

**Acceptance**
- Ordinary card: exactly one “See details / RSVP” navigation action.
- Details: organizer-selected responses, including tentative interest/questions when offered.
- Explicitly invited viewer: “I'm coming” / “Can't make it” direct RSVP on the card, using the existing ActivityResponse and current capacity/cancellation rules.
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
- An invitation to **join the Group** is different from an invitation to **RSVP to a particular Activity**.

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
- Organizers cannot silently change unrelated people's response history.
- Capacity and cancellation are enforced on the server even if two people respond simultaneously.

### P0-09 — Keep people informed and cancel responsibly

**As the outing organizer,** I want to share weather/logistics changes and cancel a single outing, so responders know what has changed and I can plan the next one.

**Acceptance**
- Updates are associated with the correct Activity or Group and readable in that context by authorized recipients.
- Cancelling an occurrence preserves its identity, response history and sibling occurrences; optional reason is visible to permitted viewers.
- A cancellation is communicated in the interface. **Reliable proactive notification to every affected person is an unresolved pilot requirement**: current context updates alone do not guarantee delivery or attention.
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

### J-08 — Janine handles space and attendance

**Given** the hike has a limited number of spaces, **when** people commit concurrently, **then** only available places are consumed. **When** full, another invited member cannot commit, but can decline; existing valid choices and response history remain coherent.

**Checkpoint:** Janine can identify committed people, not merely all “interested” people. The roster should be useful for practical day-of coordination.

### J-09 — Janine sends a weather or trailhead update

**Given** a change of weather or meeting location, **when** Janine posts an Activity-specific update, **then** permitted responders can see it in that Activity and Group members do not automatically receive an unrelated global post.

**Pilot blocker to investigate:** how will participants become aware of time-sensitive updates? If an actual trail outing depends on an email or other notification, scope and test that explicitly. An update visible only to people who return to Details may not meet real-world safety expectations.

### J-10 — Janine cancels one hike and schedules the next

**Given** a storm cancellation, **when** Janine cancels Saturday's hike with a reason, **then** its card/Details mark it cancelled and prior replies survive. The Group and Series remain intact; she can create a replacement/next outing from the Series without re-entering every default.

**Checkpoint:** cancellation awareness, response preservation, and no accidental cancellation of other occurrences.

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
| **Bobby** | Theme-park trip in several weeks, date TBD | Indicate interest before voting on dates/cost | Next |
| **Cindy** | Find someone for a concert with unsettled plans | Shared outing, possible dates, ticket implications | Next |
| **Jan (D&D)** | Weekly game with a fixed time and player count | Reusable Series, recurring social context, specific attendance | Next |
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

## 6. Disagreements and decisions requiring explicit resolution

### 6.1 Group-first navigation — resolved

The older model prioritizes browsing Groups, joining them, then attending Events. The current model is activity-first. Groups and Series remain independently useful but optional; do not restore a mandatory Group→Event dependency.

### 6.2 Direct/group invitations versus discovery — resolved by issue #60

Invitation means “the organizer is asking *you* for an attendance answer”; it does not mean an Activity is an invitation-only subtype. A public Activity can simultaneously invite particular users. Neither direct nor Group-derived invitations confer visibility. General ActivityResponse choices and Interested defaults remain unchanged.

### 6.3 Circles, boards and messaging — deferred

Older Circle objects, mandatory Group discussion boards and generalized message history are not a design mandate. Need lightweight trust, privacy and coordination; choose new social features from observed use.

### 6.4 Fee models — constrained

The old story list grants Group organizers member/event fees. Belong's later product direction rejects ordinary organizer tolls and monetization of participation/reach. Activities may disclose real costs; enabling collection, shared-cost transactions or paid institutional events requires separate product/security decisions.

### 6.5 Reuse versus automatic recurrence — resolved for now

A Series stores reusable defaults. It does not automatically schedule recurring occurrences. Any future scheduler must be explicitly requested and designed.

### 6.6 Visibility versus membership — resolved

A Group association does not itself decide who may see or answer the Activity. The Activity's own audience remains authoritative. Any future Group-only visibility mode needs explicit product/authorization design.

### 6.7 Editing and cancellation awareness — still open for a real pilot

The original stories assume users can modify/delete cards and that a cancellation reaches affected people. Confirm the exact present edit capabilities, and test whether update/cancellation awareness is operationally adequate for real hikes. Do not claim “notification” merely because an update is stored.

### 6.8 Open-ended activity lifecycle — open, issue #48

Expiration, sort order and visibility of dateless or stale Activity opportunities need explicit rules. A “sometime” proto-intent cannot be treated as an error or left at the mercy of backend NULL ordering.

### 6.9 Public-pilot privacy and abuse — open

Verify reporting, blocking, private profiles, moderation, consent, data retention, invitations and safeguards rather than treating the old feature inventory as proof of implementation. The older proposed ability for administrators to read message history is especially sensitive and must be narrowed by clear policy and authorization.

### 6.10 Janine's pilot access and external email — open operational gate

Current repository status is not proof that Janine can receive signup and invitation email from the intended deployment. Validate signup-domain, external email delivery, HTTPS origin, access restrictions and account recovery end-to-end before calling her pilot ready.

## 7. Proposed implementation/validation sequence

**Stage A — Janine's first real walkthrough:** external signup, Group creation, real invitations and acceptance, Series creation, first hike, invitation-based and ordinary RSVP, roster, update, cancellation, next hike. Reuse existing Django functionality; **file issues only for evidenced gaps**. Test with Janine and a few actual hikers before broadening.

**Stage B — Fix what the walkthrough exposes:** simplify Group/Activity create flows, any missing practical hike details, direct invitation convenience, attendee update awareness, edit/replan behavior, safety and pilot reliability.

**Stage C — Expand proto-intent:** Bobby's time-TBD planning, Greg/Peter immediate activities, Jake persistent openness, and gentle introductions. Observe actual participation before constructing a complex relationship graph.

**Stage D — Trust-intensive cases:** aid, mentoring, minors-adjacent activities, transactions, broad stranger messaging and governance-edge scenarios receive dedicated privacy/safety/product work before launch.

## 8. Traceability and review discipline

For each future GitHub issue, reference (a) a story ID or named scenario, (b) user-visible behavior, (c) explicit exclusions, and (d) end-to-end acceptance. Do not convert historical examples into automatic commitments. When implementation diverges, record the decision in issue/PR and revise this document when it changes the durable model.

**Pilot readiness is a real human test, not merely a passing automated suite.** The initial proof is that Janine and her hikers can independently make a hike happen and then want to do it again.
