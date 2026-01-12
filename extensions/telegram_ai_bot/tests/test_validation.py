import unittest

from core.validation import validate_config


class TestValidateConfig(unittest.TestCase):
    def test_valid_config(self):
        ok, err = validate_config(
            {
                "priority": ["security", "funding", "protocol", "regulation"],
                "block_keywords": [],
                "allow_keywords": [],
            }
        )
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_invalid_priority_length(self):
        ok, err = validate_config(
            {
                "priority": ["security", "funding"],
                "block_keywords": [],
                "allow_keywords": [],
            }
        )
        self.assertFalse(ok)
        self.assertIn("4", err)

