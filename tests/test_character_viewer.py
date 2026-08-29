import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CharacterViewerSizingTests(unittest.TestCase):
    def test_compact_wardrobe_preview_uses_its_real_container_size(self):
        script = (ROOT / "characters.js").read_text(encoding="utf-8")
        styles = (ROOT / "app.css").read_text(encoding="utf-8")

        self.assertIn("Math.max(container.clientWidth, 1)", script)
        self.assertIn("Math.max(container.clientHeight, 1)", script)
        self.assertNotIn("Math.max(container.clientWidth, 280)", script)
        self.assertIn(".wardrobe-character-stage canvas", styles)
        self.assertIn("width: 100% !important; height: 100% !important", styles)


if __name__ == "__main__":
    unittest.main()
