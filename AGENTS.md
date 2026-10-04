# Belong development

This Django repository is the authoritative Belong implementation.

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
