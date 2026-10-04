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
