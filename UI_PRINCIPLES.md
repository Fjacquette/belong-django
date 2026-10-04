# Belong UI principles

- Less UI is better. Every visible element must earn its space.
- Prefer direct actions over modes, multi-step controls, and configuration.
- Group controls by the user's task, not by implementation object.
- Do not show controls for features that do not work yet.
- Prefer meaning and data over decoration and ornamental chrome.
- Keep activity cards rapidly scannable.
- Mobile is a first-class layout, not desktop squeezed narrower.
- Avoid redundant labels, headers, badges, and explanations when context already communicates meaning.
- Belong is not Facebook, Reddit, Meetup, or a generic SaaS dashboard.

## Interaction grammar

Controls must communicate what they are by both semantics and appearance. Do not make clickable text masquerade as a label, or make unlike interactions look interchangeable.

- **Plain text** communicates information only. It is never clickable.
- **Links** navigate to another page, resource, or location. They should look recognizably navigational (for example, established navigation styling or underlined text where appropriate).
- **Buttons** execute an action now: submit, create, save, delete, hide, respond, search, apply, cancel, etc. Buttons should look like actionable controls, not plain text labels.
- **Toggle / view-mode controls** change a persistent binary or mutually exclusive view state without navigating. Use an explicit switch, pressed-state button, or preferably a compact segmented control when there are two named modes. The active state must be visually obvious.
- **Checkboxes** represent independent boolean choices. Use them when multiple choices may coexist.
- **Radio buttons / segmented choices** represent mutually exclusive choices within one dimension.
- **Menus** contain a set of secondary or infrequent actions/navigation choices. Their trigger must look like a control and indicate that it opens a menu; do not use a menu merely to hide primary actions.
- **Disclosure controls** expand/collapse content in place. Use a clear disclosure affordance (such as a chevron/details control) and do not style it as ordinary navigation.
- **Text that acts like a button is prohibited** unless it is unmistakably styled as an action according to the rules above.

Additional consistency rules:

- Same semantics => same visual family. Peer buttons, links, toggles, and menu triggers should be styled consistently.
- Different semantics should not be made to look identical just because doing so is fashionable elsewhere on the web.
- Controls belong near the thing they affect. Search/filter controls belong with discovery; card-layout/view controls belong with the activity results, not inside filter controls.
- Do not hide essential interaction behind hover, accidental click targets, or ambiguous labels.
- State-changing controls must visibly expose their current state when that state matters.
- Navigation uses links; mutations use buttons. Hide is private state, separate from participation.
