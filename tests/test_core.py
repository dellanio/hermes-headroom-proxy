import unittest
from headroom_proxy.core import Settings

class SettingsTests(unittest.TestCase):
    def test_defaults_and_strict_validation(self):
        s = Settings()
        self.assertTrue(s.autostart)
        self.assertEqual(s.port, 8787)
        for kwargs in ({'port': True}, {'port': 0}, {'autostart': 'false'}, {'providers': ['openai-codex']}):
            with self.assertRaises(ValueError):
                Settings(**kwargs)

if __name__ == '__main__':
    unittest.main()
