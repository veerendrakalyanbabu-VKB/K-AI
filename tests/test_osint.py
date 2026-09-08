import unittest
from app.osint import normalize_gdacs

class GdacsTest(unittest.TestCase):
    def test_positions_dates_and_deduplication(self):
        row = '<item><guid>x</guid><title>Flood</title><georss:point>17 78</georss:point><pubDate>Tue, 08 Sep 2026 10:00:00 GMT</pubDate></item>'
        xml = '<rss xmlns:georss="http://www.georss.org/georss"><channel>' + row + row + '<item><guid>bad</guid><georss:point>99 78</georss:point></item></channel></rss>'
        items = normalize_gdacs(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["lat"], 17)
        self.assertEqual(items[0]["time"], "2026-09-08T10:00:00+00:00")
        self.assertEqual(items[0]["layer"], "osint")

    def test_unsafe_and_wrong_payloads(self):
        for xml in [None, "<html/>", '<!DOCTYPE rss><rss/>']:
            with self.assertRaises(ValueError):
                normalize_gdacs(xml)
