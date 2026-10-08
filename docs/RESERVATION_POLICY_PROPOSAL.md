# Capacity, admission, registration and payment policies — proposal for review

**Status: D1/D2 and D3 free holds/optional waitlists implemented; financial policies remain proposed.** Design basis for
[#76](https://github.com/Fjacquette/belong-django/issues/76), using the reviewed
[#74 participation model](PARTICIPATION_MODEL_PROPOSAL.md). Assessed baseline:
original design master `b2fd166`, including #75 / PR #82; D1 builds from master
`63aefd9` (merged proposal PR #83). D2 builds from merged D1 master `9a3fbd0`.
D3 builds from merged D2 master `d59afed`. No payment processing or existing-data conversion is implemented. Paid hold/queue/provider terms below remain proposals.

## D1 implementation boundary

An explicitly selected version 4 ongoing Activity hosts one OngoingOpportunity
capability, with immutable approval-secures-place policy/version and a separate
optional player limit. It is not a new Activity subtype or a Series/Group membership.
Only new one-off creation offers this pattern; existing null/version 1/2/3 Activities,
Series and all historical data stay on their own authority.

EnrollmentRequest retains each explicit request and its closure/withdrawal evidence;
AdmissionDecision separately retains authorized actor/result/time. Approval creates
OngoingEnrollment and, for a limited pool, CohortPlace in the same occurrence-locked
transaction. Full approval leaves the request undecided. Unlimited approval creates
no place row. Denial closes the request; withdrawal closes it, ends any enrollment
and records any place release without deleting history. New explicit re-request
has a new identity; stale forms cannot withdraw/approve a newer request. There is
no waitlist, hold, approval-only eligibility mode, money or automatic admission.

Each linked meeting is an ordinary independent Activity. An organizer can create
one with a fresh scheduled/free default and independent schedule/capacity, copying
no people or prior responses/invitations. The link adds no enrollment/Group gate to
attendance; such admission prerequisites remain later scoped work. Meeting withdrawal
or cancellation does not end cohort enrollment; cohort withdrawal leaves existing
meeting answers untouched. Cancelling the ongoing surface closes its flows and
freezes historical requests/enrollments/places without cancelling separate meetings.
D1 does not offer pool/policy editing, organizer revocation of enrolled people,
Series enrollment defaults or conversion of existing secured free places.

Audience checks still gate request, approval and Details disclosure; lost access or
Group membership never silently deletes a secured place/history. Own Details shows
only one's own request history; the authorized organizer roster shows all admission,
enrollment and place dimensions. Only actual active enrollees qualify for ongoing
updates/cancellation via the existing consent/verified-email/access/sender controls;
pending requests/invitation alone do not subscribe. Approval/denial are in-app
outcomes, with no new decision-email event or delivery promise. Existing free-event
and poll notification authorities/history remain unchanged.

## D2 implementation boundary

New one-off Activities may explicitly select version 5 Registration. RegistrationTarget
is an immutable occurrence-scoped snapshot: USD quote (exact amount, free = zero),
version, admission, allocation trigger and optional independent capacity. Creator
cost fields initialize that quote; later display-cost changes and participant POST
amount/currency fields cannot change agreed terms. No existing Activity, Series,
poll or D1 opportunity is converted. D1 policies stay unchanged.

Open admission needs no decision. Request-required admission needs an authorized
organizer decision. Invitation-required admission explicitly accepts the Activity's
current direct invitation or its enabled invitation to active associated Group members;
unrelated invitations never count. Audience access remains independently required.
Invitation acceptance/submission creates no attendance, confirmation or allocation.
Group membership is never generally required. Lost invitation/access blocks new claims;
it does not silently revoke an already secured entitlement or remove history.

RegistrationRequest references its immutable quote/target and retains its identity,
submission and withdrawal. RegistrationAdmission separately records actor/result/time.
**Eligibility only** approval consumes nothing, even if the pool is full. For free
quotes a separate **Claim free place** POST rechecks admission/lifecycle under the
occurrence lock and creates FreeRegistration plus RegistrationPlace only when limited.
**Approval secures a free place** is selectable only with request-required admission
and a zero quote; decision, free confirmation and limited allocation are atomic.
Full approval leaves the request pending; full claim leaves the person eligible.
Unlimited free confirmation creates no artificial allocation row. No automatic
allocation on submission and no queue/promotion exist.

Positive quotes are eligibility-only. Details/roster show Payment required — unavailable,
no secured place and no paid/confirmed registration. There is no checkout, payment
record, capture claim, provider simulation, hold or receipt promise. Declining/denying
and withdrawing retain history; withdrawing a free confirmation ends it and releases
its limited place. Reapplying requires a new request identity; stale forms cannot
change the newer request. Cancellation closes all mutations and qualifies retained
confirmation as before cancellation, without erasing any evidence.

Details shows only the viewer's registration history; the authorized roster separates
admission, place, payment requirement and derived readiness. Cards navigate to Details
and expose concise current state without mutations. Native and HTMX submissions retain
safe Discover query state. Only actual active free registrations enter the existing
update/cancellation recipient adapters, still subject to consent, verified email,
access and sender controls. Pending, approved eligibility-only, invitation and paid
requests alone do not subscribe. Admission decisions do not create new email events.
Organizer revocation, policy editing, Series registration and financial/queue/expiry
infrastructure remain later milestones. All D2 audit models are read-only in admin.

## D3 implementation boundary — free reservations only

Creators may explicitly opt into **10-minute free reservation holds**, with an optional
**FIFO waitlist / 24-hour offers**, on a newly created capped free Registration target
with eligibility-only admission. FreeReservationPool is a separate capability; no
existing target acquires it and no ordinary RSVP, poll or D1 enrollment is changed.
Paid, unlimited and approval-secures-place targets cannot enable this variant. Quote,
admission, allocation and waitlist selection remain immutable. One place per person;
no checkout, money, payment-ready claim or provider operation exists.

A hold counts against capacity but is not FreeRegistration, secured allocation or
attendance. Explicit confirmation atomically ends that exact live hold/offer and
creates free registration plus its secured place. Acquisition/confirmation/expiry/
release/promotion/cancellation serialize on the owning Activity, before touching
registration, queue and hold records. Limited capacity enforces secured places +
live holds/offers <= current pool limit. The D2 claim endpoint cannot bypass holds.
`now < expires_at` is live; equality is expired. Deadlines and identities cannot be
edited or renewed. GET derives expiry without writing or promoting; every valid
reservation/registration mutation reclaims expiry and promotes before allocation.
**Check availability** is an explicit POST for queued people. Worker delay cannot
trap capacity or let newcomers pass eligible FIFO entries.

Queue joining is explicit, available when full, and requires current admission and
audience access. Pending approval, a full failure or an invitation never queues anyone.
Server-assigned entry ID supplies FIFO order, independent of registration timestamp.
On release/expiry/capacity increase, oldest eligible queued people receive protected
24-hour offer holds, never automatic confirmation. Decline/withdrawal/expiry records
closure and promotes the next eligible person. Lost admission/access closes unconfirmed
holds/entries with an ineligible reason; secured registrations survive invitation loss.
Expired offers do not regain priority: explicit rejoin creates a new tail entry (or an
explicit new direct hold may compete when no eligible queue exhausts available capacity).
Stale hold/entry/request IDs cannot change newer attempts. Repeated acquisition,
promotion, acceptance, release and cleanup preserve identity/deadline and outcomes.

FreeWaitlistEntry and FreeReservationHold retain deadlines, creation/closure timestamps,
reasons and links to the immutable registration request. Activity cancellation ends
unconfirmed holds/offers/queue entries with cancellation context and prevents promotion;
secured free registrations and all historical evidence remain retained under D2's
cancellation qualification. Existing pending registrations remain historical requests.

Only D3 pool capacity can be managed: authorized organizers submit the current pool
revision; reductions below secured places + live holds/offers are rejected. Increasing
capacity promotes without confirmation. FreePoolCapacityChange retains actor, prior/
new limit, revision and time; the target's original quote/capacity snapshot is unchanged.
Other policy editing and revocation remain unavailable. All new models are read-only
in admin; supported mutations go through the serialized services.

Offers have one durable ActivityNotificationEvent per hold, in addition to their in-app
history/deadline. Email uses existing default-off consent, verified-address, audience,
sender authority, shared quota and bounded-retry controls. Failed/opted-out delivery
never extends or retracts an offer. Dispatch rechecks its deadline and admission;
late or ended offers are skipped. An offer alone does not subscribe to routine updates
or cancellation notices; only confirmed free registrations retain that D2 authority.

`python manage.py expire_reservations` optionally records expiry and promotes without
participant traffic; run periodically for proactive offers. It processes at most 1,000
pools by default, with `--limit` and `--after` cursor for larger installations. No daemon,
queue server or schedule is installed by this milestone. Correct allocation still
works without it. Details/roster show secured vs held/offered counts, actual capacity,
fixed deadlines, independent admission, and retained queue/hold history. Cards navigate
with concise Held/Offered/Waitlisted state; image/description bands stay unchanged.

## Recommendation and decisions to review

Keep the free pilot running unchanged. Add future policies as explicit, versioned
choices for new opportunities, with separate facts for intent, admission, place and
payment. A registration is a request/process, not a promise of a seat. **Confirmed
requires every selected requirement to be satisfied and any limited place secured.**
Going remains intended attendance, never proof of physical presence.

| Decision | Proposed choice for review | Alternative requiring explicit approval |
| --- | --- | --- |
| Free capped hike | Existing first explicit confirmation wins the serialized free place; no holds or waitlist | New admission or queue policy must be explicitly selected on a new flow |
| Ongoing D&D | Request approval for an explicit ongoing opportunity; approval atomically secures a free cohort place | Approval establishes eligibility only; the person must separately claim a place |
| Paid 12-seat class | Open admission, no customer checkout hold, first eligible payment-ready request to win the serialized claim proceeds to capture | Customer checkout holds prioritize hold acquisition rather than first payment readiness |
| Optional checkout hold | Separate policy variant; propose 10 minutes, shown before payment, no automatic extension | Duration/renewals require review and provider feasibility evidence |
| Optional waitlist | Off initially; proposed explicit opt-in FIFO queue with a 24-hour place offer | Strict payment priority cannot coexist with a queue that protects promoted places |
| Withdrawal / cancellation | Future paid policy: release participation and pursue full refund for participant withdrawal before start or organizer cancellation; never claim refund completed before provider proof | Deadlines, partial refunds, fees, after-start outcomes need product/provider review |
| Historical conversion | No conversion in the first milestone; existing free authorities remain unchanged | Separate reviewed cutover preserving current entitlements and evidence |

These defaults are recommendations, including numeric durations and refund terms.
Merging the design alone must not enable payments or make them approved terms.

## Three deliberately different scenarios

| Scenario | Scope and admission | When a place is secured | Meaning of an unanswered invitation / pending request |
| --- | --- | --- | --- |
| Janine's free capped hike | One Activity occurrence; open admission; existing audience checks | Explicit affirmative response wins capacity under the occurrence lock | No attendance or allocation; Group membership is optional |
| Jan's ongoing D&D game | One explicitly identified ongoing opportunity; e.g. five player places; organizer approval | Under the proposed approval-secures-place policy, authorized approval and cohort allocation succeed in one transaction | Request sent is pending admission, consumes no place and is not Going to next week's game |
| Paid class with 12 places | One class occurrence, or an explicitly bounded cohort covering a stated set of sessions; open admission, payment required | Verified successful capture plus its exclusive allocation, reconciled locally | Registration submitted, payment authorized or checkout started alone is not confirmed |

Example traces: Janine's last free place goes to Alice's successful confirmation;
Bob's concurrent attempt keeps his previous response. For D&D, Alice and Bob can
both request the last cohort place, but only one organizer approval can secure it;
the other stays pending with a Full result, not falsely approved-and-enrolled.
For the class, Alice may register first and abandon checkout; Bob can become
payment-ready later and win the last place. Alice must not then be charged for it.
A transient internal capture claim prevents a second capture while Bob's outcome
is being established; it does not make Bob paid or confirmed in the UI.

## Current implementation and preservation boundary

Confirmed code evidence at the assessed baseline:

- [participation.locked_activity / change_response](../activities/participation.py)
  serialize reads/mutations using a write before reads, including capacity and
  cancellation. Legacy/null configuration and version 2 scheduled/immediate intent
  count committed ActivityResponse rows. Only commitment consumes capacity;
  decline/removal release it while active, and cancellation freezes responses.
- [polls.change_attendance_locked / responses_for](../activities/polls.py) give
  finalized version 3 polls their own round-specific attendance authority. Latest
  committed AttendanceAnswer rows consume capacity; withdrawal appends history.
  Availability and old ActivityResponse evidence never count as new-round attendance.
  Finalization with existing secured legacy commitments is blocked, not converted.
- [models.Activity / ActivitySeries](../activities/models.py) have descriptive cost
  fields, occurrence capacity and immutable Activity participation configuration.
  Cost marked Paid is not payment verification. No financial ledger or ongoing
  admission/enrollment exists. [series.occurrence_initial](../activities/series.py)
  copies defaults, not people, seats or subscription/attendance commitments.
- [notifications](../activities/notifications.py) and
  [announcements](../activities/announcements.py) use the actual participation
  authority with separate consent/access checks. Future policies need explicit
  recipient adapters; inventing ActivityResponse values is not such an adapter.

This design preserves IDs, raw choices/configuration, notes, response and poll
history, invitations, prior recipient snapshots and delivery records. Unlimited
free events need no artificial seat rows. Historical over-capacity free responses
remain retained, with further commitments rejected; no automatic eviction or new
fee is introduced. No new registration/payment status goes into ActivityResponse.
The current absence of waitlists, free checkout holds and free admission review
remains unchanged. New policy fields must not silently alter old occurrences.

## Policy scope and independent records

Policy belongs to a defined participation target and version, not a new Activity
subtype. A target names either an occurrence or a bounded ongoing opportunity/cohort.
Propose a small organizer-owned ongoing opportunity record, optionally linked to
Series for defaults; exact schema belongs to the enrollment milestone. Group is
optional social context, never the implicit capacity pool or enrollment authority.

A D&D enrollment reserves an ongoing player place, not attendance at every meeting.
Each published meeting retains its own audience, explicit attendance and capacity.
An occurrence can explicitly require active enrollment as its admission prerequisite;
it must say so, rather than infer it from Group membership. The two pools are not
added together or shared accidentally. Guests need an explicitly defined occurrence
policy; withdrawing from one session does not release the cohort place. Leaving the
cohort stops future eligibility but retains past sessions and existing occurrence
answers for explicit handling. Series edits affect future copies only. A multi-session
paid class must declare whether one purchase covers the whole cohort or a single
session; do not charge/allocate one way while presenting the other.

Candidate records below are design concepts, not permission to create all tables now:

| Concept | Durable facts / scope | Current state and required distinction |
| --- | --- | --- |
| Policy snapshot | Target, version, admission rule, allocation trigger, capacity scope, optional hold/queue, quoted payment/refund terms | Immutable terms referenced by requests; never infer them from title, cost or audience |
| Intent / enrollment request | Person, target/round, explicit request or confirmation/withdrawal, time | Occurrence intent and ongoing enrollment are different; no row is a valid unanswered state |
| Admission decision | Request, authorized actor, decision/reason/time, policy version | Requested, approved, denied or revoked; open means not required. Approval only allocates when policy explicitly says so |
| Registration | Person–target process, agreed quote/version, immutable request identity and transitions | Submitted/withdrawn process; aggregate confirmed is derived from other facts, not a writable all-purpose enum |
| Place allocation | Person–pool, one place, state transitions, claim/expiry/version | Held, secured, released or expired. Holds have purpose: checkout, queue offer or internal capture claim; pending claims are not secured |
| Payment attempt / provider facts | Registration, expected amount/currency, provider object and operation IDs, authorization/capture/refund evidence | Initiated, pending, authorized, captured, failed, voided; refunds retain separate pending/completed/failed facts and cumulative amount |
| Waitlist entry / offer | Explicit opt-in, pool, admission eligibility, immutable queue sequence, offer/expiry | Queued/offered/accepted/declined/expired/withdrawn; entry alone has no allocation |
| Transition / operation journal | Actor, cause, prior/new state, idempotency identity, reconciliation outcome | Durable audit; old failures and contradictory provider facts are retained, not overwritten |

One person claims at most one active place per pool in the first scope; no party
quantities, seat trading or duplicate purchase through multiple accounts/requests.
The organizer is counted only if explicitly participating. Unlimited capacity means
no allocation requirement, but approval/payment requirements still apply. Prices
are immutable server-side quotes with currency and amount, not trusted POST fields
or mutable display strings. Provider objects and webhook event IDs are uniquely
associated with their registration; financial detail is restricted to that person
and authorized operators. Full provider payload retention and accounting fields
need provider/privacy review, not speculative storage of payment credentials.

## Admission, allocation and confirmation rules

Admission modes proposed: open; request required; invitation required. Audience
visibility remains independent of all three. An invitation-required policy must
explicitly validate the scoped invitation at action time; accepting an invitation
alone creates no intent, payment or place. It may satisfy admission only when the
policy says so. Before securing a place, lost invitation/admission eligibility blocks
new claims. After securing it, invitation revocation or loss of Group membership
must not silently erase an entitlement or refund record; explicit organizer
withdrawal/review handles that transition. Loss of audience access hides private
Activity details but must preserve safe access to one's own financial receipt and
refund outcome without leaking Activity content.

| Allocation trigger | Admission decision effect | Capacity rule |
| --- | --- | --- |
| Explicit free confirmation | Open/no approval step | Atomic confirmation and capacity decision, as today |
| Approval secures place | Approval and allocation succeed together; if full, leave request pending | First successful serialized approval wins; no approved-without-promised-place label |
| Approval establishes eligibility only | Approved means eligible, not confirmed; separate Claim place or payment follows | Recheck admission under lock when claiming; approval consumes no place |
| First payment readiness, no checkout hold | Admission must already be satisfied; authorization alone is not confirmation | First eligible verified payment-ready operation to acquire a serialized capture claim can proceed |
| Checkout-hold variant | Admission required before hold acquisition | Unexpired hold counts; payment may secure only its own live claim |

Derived **occurrence confirmed** = active occurrence + current affirmative intent +
satisfied admission + required captured payment + secured allocation when limited.
Active **ongoing enrollment** uses its cohort requirements instead of an occurrence
RSVP. Closed/cancelled is a lifecycle qualification, not erasure of past confirmation.
Failed payment leaves the person's request/intent intact but unconfirmed. Full is a
pool result, not a person status. Questions, polls, invites and external navigation
cannot satisfy the above requirements.

Every limited pool enforces `secured + capacity-consuming holds/claims <= capacity`
for new-policy data. Terminal released/expired rows do not count. Capacity changes
must reject a reduction below occupied places; explicit release/review precedes
such a change. This proposed rule must not retrospectively rewrite legacy
already-over-capacity records. No automatic policy switching with active interactions.

## Payment and last-place transaction design

No provider is selected here. A future integration must demonstrate support for the
required operations and reconciliation before enabling this policy. A browser return
URL, local saved response, or webhook arrival alone is not proof of payment. External
network calls must occur outside database locks; durable operations connect them.

Proposed no-checkout-hold sequence:

1. Submit registration and agree to a server-side quote. Authenticate, check audience,
   target/admission and policy version. Starting checkout or requesting authorization
   allocates nothing. Avoid initiating known-full checkouts, but recheck at claim time.
2. Verify provider readiness to capture the quoted amount, with applicable authorization
   validity. Under the pool lock, recheck lifecycle, current intent/admission, quote,
   allocation and operation identity. If full, queue a void of any authorization;
   do not issue capture. Otherwise create an exclusive **capture claim** and durable
   capture operation atomically. This claim consumes capacity but is not confirmation.
3. After commit, dispatch that operation using its stable provider idempotency key.
   Recheck the claim/cancellation before dispatch. A successful verified capture
   is applied under the same pool lock: claim becomes secured, payment fact is retained,
   and confirmed is derived. Dispatch retries reuse the same operation identity.
4. Definitive capture failure/void releases the claim once no charge can still succeed.
   Timeout, missing callback or ambiguous result keeps the claim capacity-consuming
   and marked Checking payment. Reconcile against provider facts before freeing it;
   never start a new capture to guess whether the first worked.

**Priority needs review:** propose durable local claim order among verified,
currently eligible payment-ready requests. Registration time, page-load time and
client timestamps give no priority. Authorization alone does not secure a place.
This is operationally defined first-pay priority, not a promise to reconstruct global
provider payment timestamps across delayed events. If a winner fails definitively,
a later ready request may claim the released place. Approval time gives priority only
under the separately named approval-secures-place policy. A customer checkout hold
instead gives temporary priority to its holder; it cannot be advertised as the same
strict no-hold first-pay policy.

Do not capture without an exclusive capacity claim. If a provider cannot support
controlled capture and durable reconciliation, this milestone is blocked; choosing
a capture-then-refund oversell workflow is a new product decision. Local state and
a provider cannot be treated as one database transaction: cancellation can race a
capture already dispatched. Preserve the claim/evidence, show cancellation with
refund pending, and compensate a late successful charge. Never allocate that claim
to a replacement user while the prior capture outcome is unknown. Refund fallback
handles exceptional confirmed late charges; it is not the normal way to sell a
place that was already unavailable.

### Idempotency, expiry, cleanup and recovery

All claim/approve/release/promote/cancel operations serialize per authoritative pool,
with a documented lock order for registration then financial records. A future
multi-pool action locks pools in stable ID order. Use unique person–pool active
allocation and provider operation/event identities as well as the lock; stale pages
and workers must carry/check target and policy versions. Repeated requests return
existing results without changing priority or creating a second charge/place.

Checkout holds and queue offers have server-side expiry. Proposed boundaries:
`now < expires_at` is live; at equality it is expired. Reclaim expired, undispatched
holds under the pool lock before any new allocation, so worker delay cannot trap
capacity. A periodic idempotent sweeper records expiry and queues eligible notices;
reads never renew a hold. Proposed checkout limit: one live hold per person/pool,
10 minutes, no extension by refresh/repeated checkout. Anti-hoarding limits and
accessibility needs must be reviewed before launch.

Before dispatch, atomically replace a live customer hold/offer with a capture claim;
a payment that becomes ready after expiry must compete for a new claim under current
policy or be voided if none is available. Ordinary expiry must **not** free a capture
claim once dispatch is possible/in flight. That claim requires verified failure,
void or reconciliation, with bounded automated retries, operator alerts and an
explicit unresolved state rather than an unsafe timeout release. A recovered worker
inspects durable operations/provider facts; it does not replay a new purchase.

Authenticated provider events must match merchant, registration, quote, amount,
currency and operation. Deduplicate event IDs, retain arrival/effective evidence,
and reconcile reordered or conflicting states before applying transitions. A refund
callback arriving before delayed capture evidence must never resurrect confirmation.
A lost callback is recoverable through provider reconciliation. Notification failure
cannot roll back a place or payment, and replay cannot resend unlimited notices.

## Optional waitlist, withdrawal and cancellation

Waitlist is explicitly selected and person-opted-in; a rejected full attempt never
automatically queues someone. Proposed ordering is server-assigned FIFO sequence
among admission-eligible people. For approval-only eligibility, unapproved requests
remain outside the place queue until approved; keep their request timestamps for
history rather than pretending they already held priority. Removal/denial withdraws
queue eligibility with an audit record.

When space opens, lock the pool and offer the oldest eligible queued person a place,
with a proposed 24-hour offer hold and durable notice. No automatic Going, charge,
Group joining or occurrence attendance. Acceptance follows the selected admission/
payment steps; decline/expiry releases once and promotes the next eligible entry.
Expired offers require explicit rejoin at the tail. If notices fail, the in-app offer
and fixed deadline remain; do not silently extend/skip recipients on email delivery.
All of those rules require product review. Enabling protected FIFO offers changes
allocation priority; do not combine them with an advertised unrestricted first-pay
race. No waitlist/hold infrastructure is in the initial free-preservation milestone.

For future paid policies, withdrawal is an explicit confirmed POST operation, not a
click-again RSVP toggle. Release secured participation and record refund due under
the agreed terms; refund pending/failed remains distinct from released capacity.
A known captured charge can be refunded while its former place is resold after
explicit release; an **unknown capture** retains its claim until resolved. Withdrawing
an uncharged held registration releases it and voids any authorization. In-flight
capture instead records stop/refund intent and stays quarantined until reconciled.

Organizer cancellation closes new requests/claims/promotions immediately. Retain
all facts, terminate idle holds/offers and pending requests with cancellation context,
queue voids/full refunds under the proposed terms, and reconcile in-flight operations.
Cancelled targets are never resold even as allocations are released. Refund success
requires provider evidence; failed/unknown refunds remain visible and actionable by
operators. After-start withdrawal, provider fees, partial refunds, dispute handling,
merchant responsibility and policy for ending a paid cohort mid-series are unresolved
launch gates. No silent financial consequence from Group leaving or Series edits.

## Details, cards, roster and notifications

Follow [UI principles](../UI_PRINCIPLES.md) and [design system](../DESIGN_SYSTEM.md).
Future labels must describe the actual current fact and next step:

| Situation | Participant Details / compact card state | Organizer roster dimensions |
| --- | --- | --- |
| Free confirmation succeeded | Going / Edit response, as today | Going and secured free count, existing authority |
| D&D request awaiting decision | Request sent / View request | Enrollment request; admission Pending; no place |
| Approval secured cohort place | Enrolled / View enrollment; no implied next-session Going | Admission Approved; cohort place Secured; separate occurrence attendance |
| Approved eligibility without place | Approved — place not secured / Claim place | Admission Approved; place None/Full; payment separately |
| Payment pending or authorized only | Complete payment or Checking payment; not Confirmed | Registration; approval; place None/Held; actual payment fact |
| Checkout hold | Place held until [time] / Complete payment | Hold purpose/deadline separate from secured total |
| Paid requirements all satisfied | Registered — place secured / View registration | Place Secured; payment Captured; occurrence intent independently |
| Withdrawal/refund pending | Withdrawn — refund pending / View status | Place Released; refund Pending/Failed/Completed, retained capture |
| Waitlisted / offered | Waitlisted / View status; Place offered until [time] / Review offer | Queue order/offer expiry, no secured count until requirements pass |

Cards keep Band 4 description-only and Band 5 concise status/navigation; complex
registration/financial mutations live on Details. Show limits, real remaining capacity,
terms, hold expiry and the effect of payment/withdrawal before action. Roster separates
request/intent, admission, secured places, active holds and payment/refunds; no single
combined enum or misleading total of everyone who interacted. Native forms, keyboard,
mobile, no-JS operation and filtered Discover returns remain required.

In-app outcomes survive email failure. Future admission, offer and registration
notices need explicit event/recipient policies; neither registration submission nor
Group membership silently subscribes to all updates. Reuse verified address, scoped
consent, visibility, sender authority, fixed canonical content, budgets and bounded
retry controls. Financial receipts/status access may require a separately reviewed
transactional channel; do not assume the current optional Activity-email preference
satisfies it or promise delivery. Never include private payment details in cards,
ordinary Activity mail or a public roster.

## Thin milestones and required evidence

| Milestone, each separately authorized | Scope | Required tests / demonstration before completion |
| --- | --- | --- |
| D0: this proposal | Review policies, priority, terms, scope and unresolved decisions | Documentation consistency and existing free-capacity regressions; no schema/UI/runtime change |
| D1: free ongoing approval/enrollment implemented | Explicit new opportunity, one cohort pool, no money/holds/queue; approval-secures-place only if approved | Two requests/one approval place; authorize organizer; decline/withdraw; unlimited cohort; independent next-session RSVP; optional Group; history and migration preservation |
| D2: registration eligibility | Explicit new registration target/quote, independent admission and derived readiness, no payment promise | Open/request/invitation modes; approval-allocates versus eligibility-only; immutable terms; no fake paid/confirmed records; Details/roster/no-JS/access/notification adapters |
| D3: free reservation policy implemented | Explicit new capped/free eligibility-only targets; fixed 10-minute holds and optional FIFO/24-hour offers; no paid checkout | Last claim, expire/claim race, stale-version/idempotent actions, cleanup without worker, duplicate promotion, offer accept/expire race, capacity reduction, cancellation races; expiry UI |
| D4: provider feasibility and separately authorized sandbox | Prove authorization/capture/void/refund/reconciliation contracts before production infrastructure | Signed/reordered/duplicate/missing callbacks; incorrect amount/currency; definitive failure and timeout; retry/crash recovery; duplicate browser requests; no new charge on replay |
| D5: separately authorized paid-class pilot | Only reviewed terms, provider and operator recovery; explicit first-pay or checkout-hold policy | 12 seats/13 ready requests: at most 12 capture claims and confirmed places; losing authorization voided without capture; last-place capture/cancel/expiry races; ambiguous capture quarantined; late-capture refund; failed refund visible; no oversell/replayed notice |

D3 is optional, not a prerequisite to choosing the no-customer-hold paid variant;
that variant still requires internal exclusive capture claims in D4/D5. Provider
sandbox tests use explicit test transports/adapters, never mark real records paid
from a mock or UI callback. Every implementation updates handoff/design docs,
tests/checks, and presents its exact committed browser-test HEAD. Passing local
tests alone does not establish external financial delivery or provider readiness.

For all milestones, regression fixtures must prove unchanged legacy ActivityResponse
fields/IDs/notes/configuration, #75 poll/attendance history, Series siblings, Group
membership, announcement recipients and past notification delivery records. Run the
existing legacy and poll-round last-seat/cancellation races alongside new ones.
Migration adds no automatic payment/admission/seat backfill; any future conversion
needs a reviewed authority cutover and explicit prior-entitlement preservation.

**Review requested:** approve or revise the policy matrix, ongoing target scope,
meaning of payment priority, hold/queue durations, financial withdrawal/cancellation
terms and recovery ownership. Keep unresolved provider/financial launch gates
explicit. Then authorize one bounded milestone; this design neither closes all of
#74/#76 implementation nor starts payment/reservation infrastructure.
