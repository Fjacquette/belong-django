from django.conf import settings


def card_layout(request):
    layout = getattr(settings, "CARD_LAYOUT", {})
    height = layout.get("height", 336)
    ratio = layout.get("width_ratio", 0.75)
    bands = layout.get("bands", [0.16, 0.16, 0.32, 0.24, 0.12])
    stack_offset = layout.get("stack_offset", 54)
    base_font = layout.get("base_font", 16)
    min_width = layout.get("min_width", 220)
    max_stack_size = layout.get("max_stack_size", 3)
    max_stack_columns = layout.get("max_stack_columns", 5)

    derived = layout.copy()
    derived["width"] = round(height * ratio)
    derived["bands_px"] = [round(height * b) for b in bands]
    derived["stack_offset"] = stack_offset
    derived["height"] = height
    derived["width_ratio"] = ratio
    derived["base_font"] = base_font
    derived["min_width"] = min_width
    derived["max_stack_size"] = max_stack_size
    derived["max_stack_columns"] = max_stack_columns

    return {"card_layout": derived}
