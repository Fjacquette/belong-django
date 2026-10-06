"""Guard the shipped CSS that determines whether card piles actually overlap."""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class CardAssetTests(SimpleTestCase):
    def test_committed_css_retains_dynamic_stack_and_spread_positioning(self):
        css = (Path(settings.BASE_DIR) / 'static/css/tailwind.css').read_text()
        stack = re.search(r'\.activity-stack\s*\{([^}]+)\}', css)
        layer = re.search(r'\.activity-stack__layer\s*\{([^}]+)\}', css)
        spread = re.search(r'\[data-stack-root\]\[data-view=["\']?all["\']?\]\s+\.activity-stack__layer\s*\{([^}]+)\}', css)
        self.assertIsNotNone(stack, 'Tailwind must retain classes created by card-view.js')
        self.assertIsNotNone(layer)
        self.assertIsNotNone(spread)
        self.assertIn('position:relative', stack.group(1))
        self.assertIn('position:absolute', layer.group(1))
        self.assertIn('top:calc(var(--stack-index', layer.group(1))
        self.assertIn('position:relative', spread.group(1))
        self.assertIn('top:auto', spread.group(1))

    def test_card_bands_preserve_image_and_compact_footer(self):
        self.assertEqual(settings.CARD_HEIGHT, 440)
        bands = [round(settings.CARD_HEIGHT * band) for band in settings.CARD_BANDS]
        self.assertEqual(bands, [64, 96, 128, 104, 48])
        self.assertEqual(settings.STACK_OFFSET, sum(bands[:2]))
        css = (Path(settings.BASE_DIR) / 'static/css/tailwind.css').read_text()
        card = re.search(r'\.activity-card\s*\{([^}]+)\}', css)
        self.assertIsNotNone(card)
        self.assertIn('var(--band-3)', card.group(1))
        self.assertIn('var(--band-5)', card.group(1))
