"""Readable response colors derived from each card's authored palette."""
import re


def response_accent(primary):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', primary or ''):
        return '#333333'
    channels = [int(primary[i:i+2], 16) for i in (1, 3, 5)]
    def luminance():
        values = [value / 255 for value in channels]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    # White is both the unselected surface and selected text. Darken the same hue
    # only when needed to meet WCAG AA for normal text in both states.
    while 1.05 / (luminance() + 0.05) < 4.5:
        channels = [int(value * 0.9) for value in channels]
    return '#' + ''.join(f'{value:02x}' for value in channels)
