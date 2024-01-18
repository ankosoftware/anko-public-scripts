import unittest

from review import extract_first_changed_line_number


class TestExtractFirstChangedLineNumber(unittest.TestCase):
  def test_change(self):
    diff = "@@ -6,6 +6,93 @@\n \"version\": \"1.0.0\" },\n"
    expected = 6
    result = extract_first_changed_line_number(diff)
    self.assertEqual(result, expected)

  def test_invalid_format(self):
    diff = "invalid diff format"
    expected = None
    result = extract_first_changed_line_number(diff)
    self.assertEqual(result, expected)

if __name__ == '__main__':
  unittest.main()
