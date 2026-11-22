"""last_changed / last_successful_com attribute regression tests.

Failure corrected: _send_attributes did
    naive.replace(tzinfo=tzlocal.get_localzone()).astimezone(pytz.utc)
With tzlocal < 3, get_localzone() returns a pytz zone, and replace() with a pytz
zone attaches its first (LMT) offset: -4:56 for America/New_York, so the
published timestamps were 4 minutes off in winter and 56 minutes off in summer.
It also relabelled (instead of converting) any timezone-aware value.
Using astimezone(timezone.utc) is correct regardless of tzlocal version.

Run: python -m unittest discover -s tests   (with requirements.txt installed)
"""
import json
import os
import sys
import time
import types
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

os.environ['TZ'] = 'America/New_York'
time.tzset()


class SendAttributes(unittest.TestCase):
    def setUp(self):
        harness.load()
        import hass_devices.base as base
        self.base = base

    def publish(self, last_changed, last_comm):
        client = mock.MagicMock()
        fake = types.SimpleNamespace(id=42, json_attribute_topic='t', json_attribute_topic_qos=0,
                                     json_attribute_topic_retain=False)
        dev = types.SimpleNamespace(lastChanged=last_changed, lastSuccessfulComm=last_comm)
        with mock.patch.object(self.base, 'get_mqtt_client', return_value=client):
            self.base.BaseStatefulHADevice._send_attributes(fake, dev)
        return json.loads(client.publish.call_args.kwargs['payload'])

    def legacy_tzlocal(self):
        """Simulate tzlocal < 3, which returned a pytz zone."""
        import pytz
        if not hasattr(self.base, 'tzlocal'):
            return mock.patch('tzlocal.get_localzone', return_value=pytz.timezone('America/New_York'))
        return mock.patch.object(self.base.tzlocal, 'get_localzone',
                                 return_value=pytz.timezone('America/New_York'))

    def test_edt_with_legacy_tzlocal(self):
        with self.legacy_tzlocal():
            out = self.publish(datetime(2026, 7, 4, 12), datetime(2026, 7, 4, 12, 0, 30))
        self.assertEqual(out['last_changed'], '2026-07-04T16:00:00.000000+0000')
        self.assertEqual(out['last_successful_com'], '2026-07-04T16:00:30.000000+0000')
        self.assertEqual(out['indigo_id'], 42)

    def test_est_with_legacy_tzlocal(self):
        with self.legacy_tzlocal():
            out = self.publish(datetime(2026, 11, 22, 16, 9, 21, 123456), datetime(2000, 1, 1))
        self.assertEqual(out['last_changed'], '2026-11-22T21:09:21.123456+0000')
        self.assertEqual(out['last_successful_com'], '2000-01-01T05:00:00.000000+0000')

    def test_aware_value_is_converted(self):
        out = self.publish(datetime(2026, 11, 22, 21, 9, 21, tzinfo=timezone.utc), datetime(2026, 1, 1))
        self.assertEqual(out['last_changed'], '2026-11-22T21:09:21.000000+0000')


if __name__ == '__main__':
    unittest.main(verbosity=2)
