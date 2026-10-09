# Invitation-only beta signup (#77)

## Deployment decision

Set `BELONG_BETA_MODE=true` for a beta deployment. Set it explicitly to `false`
for ordinary signup. Production refuses to start if the setting is absent or
invalid; existing deployments must make the choice, rather than being silently
switched to invitation-only signup. Dev/test default to false. `.env.local`
accepts the same key, and process environment wins for direct Django commands.
Managed launchers use that checkout's own local configuration as usual.

Turning the flag off only removes the account admission requirement. It does not
change existing accounts, invitation history, activity audiences, memberships,
participation or consent. Verified and legacy existing accounts can sign in and
recover access in either mode. Provisional/unverified signup completion is gated.
Trusted admin account creation and local fixture commands remain administrative
operations, not public registration routes.

## Ordinary codes

A superuser opens **Admin → Social → Beta admissions → Add**, supplies the intended
recipient's email, and saves. The generated 256-bit random code is displayed once
in a non-cacheable response. Send it privately with the canonical signup URL;
do not put the code in a URL, issue, PR, screenshot or public log. No automatic
beta-code email sender or distribution list is introduced. A lost code cannot be
retrieved: revoke it and issue a new one. The admin list/detail shows issue,
expiry, revocation and redemption metadata; it never shows the verifier or code.
Use the list action to revoke selected unused admissions. Code records are
read-only after issuance and cannot be deleted through admin.

Codes are always email-bound, single-use, and expire seven days after issuance.
Only a keyed SHA-256 HMAC verifier is stored, using Django's secret key and a
beta-specific domain. A secret-key change invalidates ordinary code-entry lookups;
issue replacements as needed. Already bound email proofs still recheck admission
expiry/revocation. Invitation bridges retain their source identity across key rotation
so an already consumed credential cannot become new admission. No general-purpose or bulk/shared code policy is
implemented. Admission never grants staff, organizer, Group or Activity rights.

## Email verification and redemption

Signup says **Belong is in invitation-only beta** and asks for a code issued for
the submitted email. Invalid, expired, redeemed, revoked or mismatched credentials
share a generic error; the submitted code is never echoed. Missing code is a
required-field error. Existing account email quotas still apply. Valid signup
sends the existing 24-hour email ownership proof, without creating an account or
consuming admission. Failure to deliver or abandoning setup does not burn access.

Only a successful setup POST redeems admission, in the same serialized transaction
as account creation/provisional reclamation, profile verification and proof use.
Invalid forms, capacity/rate limits or transaction failures leave the code usable.
Competing proofs/retries can create only one account. Redemption remains recorded
even if the user is later deleted. Old ungated proofs cannot create an account
while beta mode is on; their setup form can accept a current code. Recovery and
authenticated verification routes cannot mint ungated setup credentials. Regular
password recovery and verified-account email changes retain existing rules.

## Group/Activity invitation bridge

A legitimately issued, pending Group or Activity email invitation grants beta
admission without entering another code. The user explicitly chooses signup from
the valid invitation page; its server-controlled session reference and recipient
are bound into the account email proof. Email ownership verification is still
required. The original invitation consent follows that proof across browsers.

The bridge retains a keyed verifier of the original invitation digest, its original
recipient/expiry, issuer and source reference. Completion rechecks pending status,
expiry, token rotation, issuer verification/active status/current organizer authority,
suspension and Activity cancellation. Revoking/reissuing the original invitation,
or revoking its beta admission, prevents its use. The bridge is itself single-use;
failed original invitation acceptance cannot mint a second account later.

Normal invitation acceptance retains its own checks and history. A Group invitation
may grant only its original membership. An Activity invitation may grant only its
original direct invitation; it never RSVPs, joins its Group or widens the audience.
A private Activity can remain inaccessible even after beta admission. Standing
permissions, in-app invites, arbitrary URLs or supplied numeric IDs are not beta
credentials. Codes and invitations remain separate from global Activity email opt-in.

## Review evidence

Automated tests cover flag configuration, generic failures, email proof, revoked/
used/expired credentials, old/alternate endpoints, admin secrecy, rollback, retries,
three file-backed concurrent redemption races and cross-browser invitation
continuation. Browser-test exercises real native forms with JavaScript disabled,
explicit beta configuration and disposable new identities, preserving older fixtures.
Console/local mail proves application behavior only; external inbox delivery,
canonical origin, sender setup and human pilot acceptance remain separate #87 gates.
Payments remain deferred under #87.
