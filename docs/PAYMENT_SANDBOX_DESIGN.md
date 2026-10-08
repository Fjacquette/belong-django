# D4 payment provider feasibility and sandbox design

**Proposed for review, 2026-10-08; no payment implementation authorized by this document.**
For [issue #76](https://github.com/Fjacquette/belong-django/issues/76), under the
[reservation policy proposal](RESERVATION_POLICY_PROPOSAL.md). Assessed source:
master `0dddd0ca6a7d33c2a44eb2b864064206fd3a96ca`, including merged D3 / PR #86.
This iteration evaluates published provider contracts and proposes experiments.
No provider account, credentials, API calls, sandbox transactions, webhook endpoint,
SDK, schema or paid registration route has been created. D4 sandbox evidence is
still outstanding; this does not authorize D5 or close #76.

## Recommendation and review decisions

Use **Stripe as the provisional first sandbox candidate**, with one explicitly
identified sandbox merchant, USD, one-off card payments and manual capture. Use
provider-hosted Checkout for the eventual browser experiment, retaining its underlying
PaymentIntent as the authorization/capture identity. An API-only feasibility probe
comes first; a Checkout return URL never confirms payment or attendance.
Square is a credible alternative; PayPal also supports the essential operations but
adds order/authorization/capture identities and reauthorization handling. This is a
technical recommendation, not a commercial provider selection or evidence that a
particular account is approved to process Belong activities.

Review these decisions before coding:

1. Approve/revise the Stripe sandbox candidate and card-only, USD, single-occurrence
   scope. No saved-card charging, subscriptions, split payments or alternative methods.
2. Identify who sells the activity and receives funds. A single sandbox merchant
   isolates the experiment; it does **not** decide whether Belong or each organizer
   is merchant of record. Organizer payouts/marketplace onboarding require separate
   account, provider and liability review before a paid pilot.
3. Approve the first-pay interpretation: among currently eligible, provider-verified
   authorizations, the first durable capacity claim under the pool lock wins. Browser
   arrival, registration creation and webhook timestamps do not confer priority.
4. Approve retention of capacity during an uncertain capture, with operator escalation
   instead of automatic resale. No claim timeout may silently convert uncertainty
   into failure. A refund obligation remains visible until resolved.
5. Authorize the bounded sandbox experiments below separately after review. Refund
   terms, fees, cancellation rights, operator ownership and receipt/status access
   must be settled before any D5 paid launch, even if the sandbox succeeds.

## Documented provider capabilities

Official documentation was checked on 2026-10-08. These are documentation findings,
not executed results. Account availability, merchant country, supported currency,
permissions, API version and payment-method eligibility must be verified in the
chosen sandbox and later reassessed for a production merchant. No pricing comparison
or recommendation about legal/tax responsibilities is implied.

| Requirement | Stripe | Square | PayPal |
| --- | --- | --- | --- |
| Authorization without capture | Checkout `payment_intent_data.capture_method=manual`; underlying PaymentIntent becomes `requires_capture` after authorization. Restrict to cards. [S1] | `CreatePayment` with `autocomplete=false`, yielding `APPROVED`. [Q1] | Orders v2 `intent=AUTHORIZE`, then authorize the approved order; retain authorization ID separately from order ID. [P1] |
| Capture | Capture the existing PaymentIntent; verify exact full quote and resulting payment state. [S1] | `CompletePayment` for the approved payment; optional payment `version_token` detects concurrent changes. [Q2] | Payments v2 capture the authorization; retain returned capture ID, amount, currency and status. [P2] |
| Authorization lifetime | Read actual card `capture_before`; ordinary online windows vary by network/transaction, commonly 5–7 days. Do not hard-code a seven-day guarantee. [S1] | Online default seven days; `delayed_until` identifies the server deadline, and a shorter `delay_duration` is possible. Require `delay_action=CANCEL`. [Q1] | 29-day authorization window with initial three-day honor period; later capture can fail. Reauthorization produces a new ID; no reauthorization in the first experiment. [P1], [P3] |
| Void / cancel | Cancel an uncaptured PaymentIntent and verify terminal state. Checkout Session expiration and authorization cancellation are distinct operations. [S2] | `CancelPayment`; cancellation by original create idempotency key is available when its payment ID was lost. [Q1], [Q3] | Void authorization by ID; a fully captured authorization cannot be voided. [P4] |
| Refund | Refund captured money; pending and failed outcomes exist, including later failure. Provider acceptance is not proof that a customer received funds. [S3], [S6] | `RefundPayment` supports full/partial amount and required request key; refund processing has separate state. [Q4] | Refund capture ID, then retrieve refund status; statuses include `PENDING`, `COMPLETED`, `FAILED`, `CANCELLED`. [P5] |
| Idempotency | All POST operations support keys; keys can be pruned after at least 24 hours. Cached results include 500 errors. [S4], [S5] | Create/refund request keys are documented; CompletePayment exposes payment ID/version rather than a request-key field. Do not assume every operation has identical deduplication. General docs do not establish a universal retention horizon. [Q2], [Q4], [Q5] | `PayPal-Request-Id` on supported operations; general documentation describes retention up to 45 days. Verify each endpoint/account contract rather than promising a uniform 45-day minimum. [P6] |
| Callbacks and recovery | Verify raw-body signature; delivery can duplicate or reorder. Retrieve underlying objects, reconcile independently of delivery. [S7] | Verify HMAC using exact notification URL/raw body; no ordering guarantee; retries stop after 24 hours. GetPayment plus refund retrieval/listing required. [Q6], [Q7] | Verify signed transmission against configured webhook ID; REST verification or cryptographic verification. Mock simulator events are not equivalent to app transaction events. [P7] |

**Feasibility conclusion:** all three have the required operation categories. None
offers an atomic transaction spanning a Belong seat and a provider charge. Stripe's
single PaymentIntent and documented error recovery make it the preferred experiment;
this remains contingent on actual evidence. Automatic capture, Stripe
`automatic_delayed`, Square `delay_action=COMPLETE`, overcapture, partial/multiple
captures and payment methods that debit during authorization are outside the proposed
contract. A provider's additional features must not weaken Belong's capacity policy.

## Preserve the existing authorities

Current `activities/registration.py` stops paid targets at eligibility; its
`secure_free` creates a `FreeRegistration`, whose model rejects a paid quote.
`activities/reservations.py` operates explicit free pools/holds/waitlists, and
`activities/participation.py` supplies the existing Activity serialization/cancellation
boundary. There is no financial operation journal or provider adapter in this source.

Future sandbox code must remain isolated from these authorities and persistent demo
data. No migration/backfill converts ActivityResponse, poll answers, admission,
ongoing enrollment, free places, D3 holds or waitlist entries into payment facts.
The experiment may model a **sandbox-only** paid pool using disposable synthetic
registrations; it must not mark real RegistrationRequest records paid from a fake
transport. Existing free capacity, poll finalization/history and enrollment remain
on their existing behavior and regression tests.

Keep four independent facts: current intent/eligibility, admission, capacity claim
or secured place, and payment/financial remedy. Authorization alone is neither a
secured place nor attendance. A customer checkout hold, the issuer's authorization
hold and an internal capture claim are three different things. Do not reuse D3's
10-minute free hold or 24-hour queue offer to expire an in-flight payment claim.

## Proposed transaction and cancellation contract

The first experiment uses **no customer checkout hold or waitlist**. An authorization
is obtained only for an authenticated, currently eligible synthetic request with an
immutable server quote. If approval is required, it precedes authorization. A change
to quote/target/intent ends that attempt; it never changes an existing charge amount.
USD is converted exactly to integer cents, never float or browser-supplied price.

Authorization is followed promptly by allocation/capture during registration; do
not hold funds until an activity weeks away. No provider window here supports an
arbitrary event-date reservation. Approval delays must occur before authorization;
deadline safety checks never extend an issuer hold or silently reauthorize a customer.

1. Obtain and retrieve the authorization in the configured merchant/mode. Check
   target/request/quote identity, currency, full capturable amount, manual capture
   configuration and actual deadline. `requires_action`/incomplete authentication
   is not payment readiness. Propose a 60-second dispatch safety margin before
   the actual authorization deadline, to validate experimentally; it is not a new
   provider guarantee or customer hold duration.
2. Under the same Activity/pool serialization boundary as allocation and cancellation,
   recheck lifecycle, current intent, audience/admission, target version, quote and
   capacity. Persist one exclusive capture claim **and** its durable operation in
   one transaction. Claims plus secured places cannot exceed the pool limit.
   The losing request gets a durable void obligation and no capture operation.
3. Dispatch outside the database lock. Before dispatch, atomically check cancellation
   and claim ownership and persist dispatch intent. No external call occurs inside
   a Django transaction. Crash after dispatch intent is ambiguous, even if the worker
   may never have reached the provider. Retrying uses the existing operation identity.
4. Retrieve/verify provider outcome. Under the pool lock, exact successful capture
   converts the claim to a secured sandbox place if the request is still acceptable.
   A definitive uncaptured terminal outcome closes the operation and releases the
   claim. Authentication/network errors, missing callbacks and 5xx never prove failure.
5. Cancellation/withdrawal/lost eligibility before dispatch closes undispatched work
   and queues void. After dispatch it prevents confirmation and starts reconciliation.
   The race between the final local check and the external capture cannot be eliminated:
   a late successful capture requires a durable compensating full-refund obligation.
   Never restore attendance on a cancelled activity or invent a replacement charge.

An uncertain capture retains its capacity claim with status **Checking payment**.
Proposed release rule: after authoritative captured outcome and a recorded remedy
obligation, cancellation can release the seat, while the refund remains independent
and visible; after verified uncaptured cancellation/failure, release normally. Do not
wait for a refund to arrive to acknowledge cancellation, or label a pending refund
completed. Admission-denied/no-seat outcomes require voiding the original authorization,
not refunding a charge that was never captured. Void failure needs recovery too.

## Proposed durable evidence and idempotency

These are logical records for review, **not migrations**:

| Record | Required evidence and uniqueness |
| --- | --- |
| Payment attempt | Random local identity; request/target/quote versions; merchant/account and sandbox mode; exact expected amount/currency; provider object IDs and authorization deadline; terminal history. One unresolved attempt per request; a new attempt requires proof the old one cannot charge. |
| Financial operation journal / outbox | Unique logical create/authorize/capture/void/refund operation, immutable payload digest, stable non-PII provider key, first dispatch time, known retry horizon, provider request/resource IDs, dispatch lease, retry/result/uncertainty evidence. One capture operation per attempt; never rotate a key because of a timeout. |
| Capacity claim | Unique request/attempt ownership, pool, serialized order and lifecycle; counts while undispatched or uncertain; atomically replaced by a secured place or explicitly released. Financial retry lease expiry never frees capacity. |
| Verified event inbox | Unique provider/account/mode/event ID, validated receipt time, object IDs, minimal normalized facts, processing state. A distinct event representing the same operation must not repeat confirmation, refund or notice. |
| Refund obligation and operation | Reason, captured resource, immutable requested amount, authorized actor, cumulative successful plus pending/unknown refund budget, independent status/history. Concurrent refunds cannot exceed captured funds. |
| Reconciliation case | Last provider read, discrepant facts, next bounded retry, age/deadline, owner/escalation and audited resolution. No operator edit that fabricates paid status or ignores a possible charge. |

Provider request-key retention is shorter than financial record retention. For Stripe,
stop automatic mutation replay before the 24-hour minimum horizon, with a conservative
margin measured from first dispatch; retrieve/reconcile instead. Never replay a create
or refund blindly after pruning, even with the old key. If an ID was lost, correlate
opaque local metadata, provider request logs/events and scoped object lists; a missing
search result is not proof of non-execution. Unresolved cases require operator/provider
investigation. A replacement operation requires an audited definitive resolution,
not a user retry or a stale webhook.

Stripe documents indeterminate 500s that can later produce side effects [S5]. API
and webhook workers must share one local reducer; verify account/mode, identity,
amount/currency and authoritative current object state before application. Do not
sort event snapshots by timestamps to overwrite state: financial facts can change
later, including a previously successful refund failing [S6]. Keep observations/history
and derive current state; never use a single monotonically increasing paid enum.

## Reconciliation, operator recovery and participant access

Signed callbacks are triggers, not the sole delivery mechanism. Persist verified
receipt before acknowledging; failed inbox persistence must remain retryable. Process
outside the HTTP request, deduplicate, and retrieve relevant payment/charge/refund.
Reject incorrect signatures, mode/account, currency, amount, quote or ownership.
Only the dedicated provider endpoint would be exempt from CSRF; user forms retain it.
For PayPal certificate verification, any eventual fetching must validate allowed
provider HTTPS origins rather than trust an arbitrary certificate URL.

Propose a bounded management-command worker with durable retry state first, without
adding a broker solely for D4. Poll unresolved attempts/voids/refunds, approaching
authorization deadlines and interrupted operations even when callbacks never arrive.
Use provider-request backoff/rate limits, serialized per-attempt reduction, and a
separate audited reconciliation schedule. Provider outage pauses new financial
dispatch; it does not allow seats to be released by assumption. Alert an assigned
operator for uncertainty older than a proposed five minutes, failed remedies and
approaching deadlines; these timings need review and sandbox evidence.

Also reconcile provider-to-local: enumerate scoped objects for the experiment with
pagination, overlap and a durable cursor; find orphan charges, manual Dashboard
captures/refunds and unexpected amount/mode/account. Unknown captures must create a
case, never silently count as attendance. Compare captured/refunded gross amounts
separately from fees/net/balance transactions. For future live operation, reconciliation
must also cover settlement/payouts, disputes/reversals and provider reports; a successful
capture does not prove cash arrived in a bank. Stripe's balance report supplies
itemized financial activity, but that is distinct from a seat audit [S8]. D4 may
exercise synthetic report comparison, not certify live settlement.

Before a paid pilot, give a participant authenticated access to **their own** financial
status/remedy even after Activity audience access is removed (current Details can
return 404). No Activity details or other participants' finance information leaks.
Private operator recovery is distinct from organizer rosters. Existing optional
Activity-update email consent is not automatically a receipt policy; define provider
receipts/transactional communications and failure handling separately. Capture,
confirmation, cancellation and financial notices each deduplicate by logical outcome.

## Separately authorized sandbox experiment

Use a dedicated provider general sandbox, test credentials and disposable local DB,
synthetic users and card fixtures. Keep production database, browser-test fixtures,
email configuration and secrets untouched. Verify the expected account using provider
retrieval and reject live-mode resources/keys before any mutation; key prefix alone
is not sufficient. No fallback to live configuration. Pin SDK/request and webhook
API versions, record them in evidence, and scope credentials to required operations.
Hosted Checkout/tokenization keeps PAN/CVC out of Django; never log raw financial
payloads, client secrets, card fields or credential values. Retain only reviewed
minimal facts and opaque identifiers with a stated evidence retention/access policy.

Proposed sequence, each step recording actual results rather than inferred success:

1. **Provider contract probe:** create/authorize a test payment, retrieve it, full
   capture, separate uncaptured cancel, full refund and status retrieval with stable
   keys. Inspect exact object IDs, amounts, deadlines, request IDs and state transitions.
2. **Isolated capacity harness:** bind those operations to a disposable synthetic pool,
   claim/journal/inbox/reconciliation prototypes, transport fault injection and explicit
   transaction boundaries. Fake transports test local crashes; only actual sandbox
   objects establish provider behavior. No paid flow on normal Activity routes.
3. **Sandbox browser demonstration:** hosted card collection/authentication, repeated
   submit/back/return, private status and cancellation. Clearly labelled sandbox
   exercise on a separate environment; synthetic success never writes paid records
   into the persistent demo. Any future app iteration gets its exact committed preview;
   this pure documentation iteration leaves D3 browser-test running.

| Required experiment | Evidence / pass condition | Method |
| --- | --- | --- |
| Authorize, capture, void, refund | Separate real sandbox object histories and exact expected amounts; no capture on voided loser; refund has its own result | Provider sandbox APIs and retrieval |
| Authentication incomplete/failed/abandoned | No readiness/claim/attendance from a browser return or challenge start | Hosted UI + documented card fixtures [S6] |
| 12 seats / 13 payment-ready requests | At most 12 active claims/secured places and captures; remaining authorization voided; serialized claim order retained | Concurrent DB connections plus real sandbox objects |
| Last-seat/cancel and withdraw/access/admission races | No confirmation after closure; undispatched work voided, late capture creates one refund obligation | Barriers before/after dispatch + retrieval |
| Lost response, 500, process crash | Same operation/key survives restart; claim quarantined; no duplicate charge or new attempt | Fault injection around actual API call + provider read; injected errors explicitly labelled |
| Duplicate browser/API requests | One attempt and capture operation; immutable parameters; repeat result/status only | Concurrent/replayed requests |
| Duplicate/reordered/missing callbacks | Verified inbox survives restart; no duplicate effects; missed outcomes discovered by polling | Actual signed events/re-delivery + local controlled replay/drop |
| Forged/wrong mode/account/amount/currency/quote | No financial or place transition; visible discrepancy case where appropriate | Invalid signatures and synthetic contract faults; actual sandbox objects where supported |
| Deadline passed/authorization revoked | No new capture dispatch past safety boundary; resolve uncaptured state before releasing uncertain claims | Provider deadline retrieval plus fault/clock-controlled boundary tests; real expiry if supported |
| Retry horizon exhausted; lost object ID | No blind POST replay/new key; scoped discovery or operator case; capacity remains safe | Inject aged journal, lost response, unavailable lookup |
| Refund pending then success; initial success then failure | Own financial status updates correctly, obligations retained, no duplicate refund | Documented asynchronous refund fixtures [S6] |
| Concurrent/partial refund attempts | Successful + outstanding budget never exceeds capture; partial refund never masquerades as full refund | API probe + local serialized refund ledger |
| Provider outage/worker down | Pending cases survive; new dispatch pauses; bounded recovery does not resell unknown seat | Controlled network failure, restart and rate-limit faults |
| Dashboard/orphan mutation and report discrepancy | Reverse reconciliation discovers unexpected charge/refund and creates audited case | Sandbox manual action, scoped list/report comparison |
| Legacy isolation | Free capacity/hold/queue, poll/history and ongoing enrollment regressions pass; demo data unchanged | Existing Django tests and disposable fixtures |

Stripe sandbox transactions do not use card networks [S9]. Its documented fixtures
cover 3DS and asynchronous refunds [S6], but sandbox success cannot establish actual
issuer timing, live fraud behavior, payout settlement, commercial eligibility or
financial liability. Square sandbox supports online test tokens, not card-present
scenarios [Q8]. PayPal sandbox authorizations **do not expire after 29 days**; test
expiry errors through its documented negative testing [P1]. A mocked expiry or 500
must be reported as injected, never as a provider-observed real transaction outcome.

D4 completion requires an evidence artifact containing commit/API versions,
non-sensitive sandbox account identifiers, case-by-case actual IDs/statuses/request
IDs, provider reads, local operation/claim history, command/test results and unresolved
capability gaps. No credentials or raw payloads enter GitHub. All experiments are
**not run** in this iteration. Review this design before authorizing implementation.

## Official sources

- **S1:** [Stripe separate authorization/capture](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method).
- **S2:** [Stripe PaymentIntent cancellation](https://docs.stripe.com/api/payment_intents/cancel).
- **S3:** [Stripe refunds and failures](https://docs.stripe.com/refunds).
- **S4:** [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests).
- **S5:** [Stripe advanced error handling](https://docs.stripe.com/error-low-level).
- **S6:** [Stripe test authentication and asynchronous refunds](https://docs.stripe.com/testing).
- **S7:** [Stripe webhook verification, delivery and deduplication](https://docs.stripe.com/webhooks).
- **S8:** [Stripe balance reconciliation report](https://docs.stripe.com/reports/balance).
- **S9:** [Stripe isolated sandboxes and limitations](https://docs.stripe.com/sandboxes).
- **Q1:** [Square delayed capture](https://developer.squareup.com/docs/payments-api/take-payments/card-payments/delayed-capture).
- **Q2:** [Square CompletePayment contract](https://developer.squareup.com/reference/square/payments-api/complete-payment).
- **Q3:** [Square cancel by create idempotency key](https://developer.squareup.com/reference/square/payments-api/cancel-payment-by-idempotency-key).
- **Q4:** [Square RefundPayment](https://developer.squareup.com/reference/square/refunds-api/refund-payment) and [refund states](https://developer.squareup.com/docs/payments-api/refund-payments).
- **Q5:** [Square idempotency semantics](https://developer.squareup.com/docs/build-basics/common-api-patterns/idempotency).
- **Q6:** [Square signature verification](https://developer.squareup.com/docs/webhooks/step3validate).
- **Q7:** [Square webhook ordering and retry limits](https://developer.squareup.com/docs/webhooks/overview).
- **Q8:** [Square sandbox payment limitations](https://developer.squareup.com/docs/devtools/sandbox/payments).
- **P1:** [PayPal authorize/delay capture and sandbox expiry limitation](https://developer.paypal.com/checkout/delay-capture/).
- **P2:** [PayPal capture authorized payment](https://developer.paypal.com/api/payments/v2/authorizations-capture/).
- **P3:** [PayPal authorization/honor and reauthorization](https://developer.paypal.com/payment-methods/auth-honor/).
- **P4:** [PayPal void authorization](https://developer.paypal.com/api/payments/v2/authorizations-void/).
- **P5:** [PayPal refund capture](https://developer.paypal.com/api/payments/v2/captures-refund) and [refund status](https://developer.paypal.com/api/payments/v2/definitions/refund/).
- **P6:** [PayPal request idempotency and endpoint support](https://developer.paypal.com/api/rest/requests/).
- **P7:** [PayPal signed webhooks and simulator limitations](https://developer.paypal.com/api/rest/webhooks/rest/).

[S1]: https://docs.stripe.com/payments/place-a-hold-on-a-payment-method
[S2]: https://docs.stripe.com/api/payment_intents/cancel
[S3]: https://docs.stripe.com/refunds
[S4]: https://docs.stripe.com/api/idempotent_requests
[S5]: https://docs.stripe.com/error-low-level
[S6]: https://docs.stripe.com/testing
[S7]: https://docs.stripe.com/webhooks
[S8]: https://docs.stripe.com/reports/balance
[S9]: https://docs.stripe.com/sandboxes
[Q1]: https://developer.squareup.com/docs/payments-api/take-payments/card-payments/delayed-capture
[Q2]: https://developer.squareup.com/reference/square/payments-api/complete-payment
[Q3]: https://developer.squareup.com/reference/square/payments-api/cancel-payment-by-idempotency-key
[Q4]: https://developer.squareup.com/reference/square/refunds-api/refund-payment
[Q5]: https://developer.squareup.com/docs/build-basics/common-api-patterns/idempotency
[Q6]: https://developer.squareup.com/docs/webhooks/step3validate
[Q7]: https://developer.squareup.com/docs/webhooks/overview
[Q8]: https://developer.squareup.com/docs/devtools/sandbox/payments
[P1]: https://developer.paypal.com/checkout/delay-capture/
[P2]: https://developer.paypal.com/api/payments/v2/authorizations-capture/
[P3]: https://developer.paypal.com/payment-methods/auth-honor/
[P4]: https://developer.paypal.com/api/payments/v2/authorizations-void/
[P5]: https://developer.paypal.com/api/payments/v2/captures-refund
[P6]: https://developer.paypal.com/api/rest/requests/
[P7]: https://developer.paypal.com/api/rest/webhooks/rest/
