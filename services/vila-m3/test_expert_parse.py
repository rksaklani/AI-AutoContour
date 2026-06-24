"""Unit tests for structured finding extraction."""

from __future__ import annotations

import unittest

from expert_parse import parse_structured_findings, structured_description, volume_for_finding


class ExpertParseTests(unittest.TestCase):
    def test_hepatic_tumor_block(self) -> None:
        text = (
            "Possible hepatic tumor detected.\n"
            "Size: 2.4 cm\n"
            "Location: Segment VIII\n"
            "Confidence: 94%"
        )
        findings = parse_structured_findings(text, None)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertIn("tumor", f.label.lower())
        self.assertEqual(f.size_cm, 2.4)
        self.assertAlmostEqual(f.confidence, 0.94)
        self.assertIn("VIII", f.location)
        self.assertAlmostEqual(volume_for_finding(f), 7.24, places=0)

    def test_lung_nodule_narrative(self) -> None:
        text = (
            "A pulmonary nodule is visible in the right upper lobe measuring 1.2 cm "
            "with 88% confidence."
        )
        findings = parse_structured_findings(text, None)
        self.assertGreaterEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.size_cm, 1.2)
        self.assertAlmostEqual(f.confidence, 0.88)

    def test_expert_notes_merged(self) -> None:
        vila = "Abnormality in the liver."
        expert = ["Hepatic lesion in segment VII, diameter 3.1 cm, confidence 91%"]
        findings = parse_structured_findings(vila, expert)
        self.assertGreaterEqual(len(findings), 1)
        desc = structured_description(findings[0])
        self.assertIn("cm", desc)
        self.assertIn("Confidence", desc)


if __name__ == "__main__":
    unittest.main()
