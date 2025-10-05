from django import template

register = template.Library()


@register.filter
def add_class(field, css):
    """Return field rendered with additional CSS classes."""
    attrs = field.field.widget.attrs.copy()
    existing = attrs.get("class", "")
    combined = f"{existing} {css}".strip()
    return field.as_widget(attrs={**attrs, "class": combined})
