from django import template

register = template.Library()


@register.filter
def stack_height(count, layout):
    try:
        count = int(count)
        height = layout.get('height', 336)
        offset = layout.get('stack_offset', 54)
    except (TypeError, ValueError, AttributeError):
        return 0
    if count <= 0:
        return height
    return height + max(0, count - 1) * offset


@register.filter
def stack_offset(index, layout):
    try:
        index = int(index)
        offset = layout.get('stack_offset', 54)
    except (TypeError, ValueError, AttributeError):
        return 0
    return index * offset

@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (TypeError, ValueError):
        return 0

