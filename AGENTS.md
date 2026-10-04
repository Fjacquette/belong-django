# Belong development

This Django repository is the authoritative Belong implementation.

Follow [UI_PRINCIPLES.md](UI_PRINCIPLES.md) for interface changes.

## Product constraints

- Belong is activity-first: shared activities create and deepen relationships.
- Support low-friction participation and proto-intent (early interest in doing
  something together); do not force every activity into a formal event/RSVP model.
- Groups may help coordination but must not gate activity participation.
- Preserve safety, kindness, accessibility, and opportunity as product constraints.
- Do not invent features or resurrect historical prototype behavior unless the
  issue explicitly requires it.
- Surface genuinely ambiguous product decisions rather than silently choosing a
  large behavioral change.

## Development workflow

- Prefer simple server-rendered Django templates and HTMX. Do not introduce React
  or unnecessary infrastructure.
- Keep changes tightly scoped to the issue.
- Add or update tests for changed behavior where practical.
- Before finishing, run `python manage.py check` and relevant Django tests
  (`python manage.py test` or targeted test labels) in the project environment.
  Follow README.md for setup; report validation results and any limitations.
- Do not commit secrets, local databases, uploaded user data,
  environment-specific configuration, or machine metadata. Preserve local data
  and stage only the intended source changes.

## Present every implementation for review

Before declaring a normal implementation iteration complete, commit the finished
source, open its PR, and run `./scripts/present-test.sh` from the main checkout.
Present that exact committed HEAD in the persistent browser-test environment on
http://127.0.0.1:8001, verify readiness, and report the preview commit SHA.
Preserve browser-test data, configuration, and secrets. Codex owns the worktree,
dependency, migration, and server mechanics; Frank should only reload his browser.
Pure documentation changes that cannot affect the running app may skip presentation.

PR descriptions explain changes and what to inspect, with wording such as
“Browser-test is running this iteration at http://127.0.0.1:8001. Review: …”.
Do not ask Frank to stop servers, refresh worktrees, migrate, or start browser-test.
