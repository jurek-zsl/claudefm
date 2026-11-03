"""Contact shadows stay on the floor and leave cached scenery reusable."""
import unittest

from claudefm.audio import AudioPlayer
from claudefm.scene import render_background
from claudefm.tui import TUI, _composite_contact_shadows


class GroundingTests(unittest.TestCase):
    def test_soft_contact_never_darkens_pixels_above_the_floor(self):
        color = (100, 150, 200)
        pixels = [[color] * 40 for _ in range(30)]
        _composite_contact_shadows(pixels, 0, 0, [(20, 26, 8, .2)])
        self.assertTrue(all(pixel == color for row in pixels[:26] for pixel in row))
        self.assertTrue(all(pixel == color for row in pixels[28:] for pixel in row))
        self.assertLess(pixels[26][19][0], pixels[26][12][0])
        self.assertGreater(pixels[26][19][0], 0)
        self.assertLess(pixels[26][19][0], pixels[27][19][0])

    def test_contact_patches_clip_safely_at_terminal_edges(self):
        pixels = [[(100, 100, 100)] * 8 for _ in range(4)]
        _composite_contact_shadows(pixels, -3, 0, [(0, 3, 7, .2)])
        self.assertEqual([len(row) for row in pixels], [8] * 4)
        self.assertEqual(pixels[:3], [[(100, 100, 100)] * 8 for _ in range(3)])
        self.assertLess(pixels[3][0][0], 100)
        _composite_contact_shadows([], 0, 0, [(0, 0, 1, .2)])

    def test_compositing_keeps_cached_scenery_pristine(self):
        player = AudioPlayer(enabled=False)
        tui = TUI(player, initial_theme='light', initial_activity='bike')
        before = render_background(80, 40, 'bike', False, 0)
        first = tui.render_lines(80, 24)
        self.assertEqual(render_background(80, 40, 'bike', False, 0), before)
        self.assertEqual(tui.render_lines(80, 24), first)


if __name__ == '__main__':
    unittest.main()
