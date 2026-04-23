import unittest

import serve


class ServeSecurityTests(unittest.TestCase):
    def test_blocks_dotfiles_and_private_dirs(self):
        blocked = [
            '/.env',
            '/.env.local',
            '/.git/config',
            '/.vercel/project.json',
            '/lib/__pycache__/x.pyc',
        ]
        for path in blocked:
            with self.subTest(path=path):
                self.assertTrue(serve.is_forbidden_static_path(path))

    def test_allows_normal_static_and_api_paths(self):
        allowed = [
            '/',
            '/index.html',
            '/data/patchnotes.json',
            '/api/stock-price?code=005930',
        ]
        for path in allowed:
            with self.subTest(path=path):
                self.assertFalse(serve.is_forbidden_static_path(path))


if __name__ == '__main__':
    unittest.main()
