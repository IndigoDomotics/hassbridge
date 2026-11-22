"""Access-token sanity check regression tests.

Failure corrected: Config called jwt.decode(token, verify=False). PyJWT 2.x
ignores `verify` and requires `algorithms`, raising DecodeError (an
InvalidTokenError), so every start logged "Access Token does not appear to be
valid." even for a valid Home Assistant long-lived token.

Run: python -m unittest discover -s tests   (with requirements.txt installed)
"""
import logging
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

import jwt  # noqa: E402

LOGGER = 'hassbridge.test.config'


def token(**claims):
    claims.setdefault('iss', 'test')
    claims.setdefault('iat', int(time.time()))
    claims.setdefault('exp', int(time.time()) + 3600)
    out = jwt.encode(claims, 'not-the-real-secret', algorithm='HS256')
    return out.decode() if isinstance(out, bytes) else out


class TokenCheck(unittest.TestCase):
    def setUp(self):
        _, self.pkg, _ = harness.load()

    def config(self, access_token):
        prefs = dict(harness.DEFAULT_PREFS, access_token=access_token)
        return self.pkg.Config(prefs, logging.getLogger(LOGGER))

    def test_valid_token_does_not_warn(self):
        with self.assertNoLogs(LOGGER, level='WARNING'):
            cfg = self.config(token())
        self.assertTrue(cfg.hass_session_headers['Authorization'].startswith('Bearer ey'))

    def test_garbage_token_warns(self):
        with self.assertLogs(LOGGER, level='WARNING') as logs:
            self.config('not-a-jwt')
        self.assertTrue(any('does not appear to be valid' in m for m in logs.output))


if __name__ == '__main__':
    unittest.main(verbosity=2)
