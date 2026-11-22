import unittest
from tracker import parse_price, qualifies

class PriceTests(unittest.TestCase):
    def test_indian_format(self):
        self.assertEqual(parse_price("₹1,23,456.50"), 12345650)
    def test_invalid(self):
        for value in ["", "₹0", "₹500 - ₹700", "Save ₹500"]:
            self.assertIsNone(parse_price(value))
    def test_threshold(self):
        self.assertTrue(qualifies(400000, 4000))
        self.assertFalse(qualifies(400001, 4000))
        self.assertFalse(qualifies(None, 4000))

if __name__ == "__main__":
    unittest.main()
