from django.conf import settings


def card_layout(request):
    layout = getattr(settings, "CARD_LAYOUT", {})
    height = layout.get("height", 336)
    ratio = layout.get("width_ratio", 0.75)
    bands = layout.get("bands", [0.16, 0.16, 0.32, 0.24, 0.12])
    stack_offset = layout.get("stack_offset", 54)

    derived = layout.copy()
    derived["width"] = round(height * ratio)
    derived["bands_px"] = [round(height * b) for b in bands]
    derived["stack_offset"] = stack_offset
    derived["height"] = height
    derived["width_ratio"] = ratio

    return {"card_layout": derived}
