"""Background-loop stability regression tests.

Failures corrected:
1. InsteonBatteryStateSensor.check_for_update called tz.localize()/normalize()
   on tzlocal.get_localzone(). tzlocal >= 3 (requirements resolve 5.x) returns a
   zoneinfo object without those methods, so every timed check raised
   AttributeError.
2. That exception propagated out of runConcurrentThread and ended the thread:
   no MQTT reconnects and no Home Assistant mapping refreshes until restart.
3. Iterating self._ha_devices while a remap or registration added entries raised
   "dictionary changed size during iteration" (seen on reconnect right after a
   new Indigo device was created).

Run: python -m unittest discover -s tests   (with requirements.txt installed)
"""
import os
import sys
import time
import types
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

os.environ['TZ'] = 'America/New_York'
time.tzset()


class BatteryCheck(unittest.TestCase):
    def setUp(self):
        harness.load()
        import insteon.devices as devices
        self.cls = devices.InsteonBatteryStateSensor

    def run_check(self, minutes_ago, limit):
        fake = types.SimpleNamespace(
            indigo_entity=types.SimpleNamespace(
                lastSuccessfulComm=datetime.now() - timedelta(minutes=minutes_ago)),
            no_comm_minutes=limit,
            _send_battery_state=mock.MagicMock(),
            _send_attributes=mock.MagicMock())
        self.cls.check_for_update(fake)
        return fake._send_battery_state.call_args.args[0]

    def test_recent_comm_is_not_low_battery(self):
        self.assertFalse(self.run_check(minutes_ago=5, limit=1440))

    def test_stale_comm_is_low_battery(self):
        self.assertTrue(self.run_check(minutes_ago=1500, limit=1440))


class ConcurrentThread(unittest.TestCase):
    def setUp(self):
        self.indigo, _, plugin = harness.load()
        self.p = plugin.Plugin('com.github.wonderslug.hassbridge', 'HassBridge', 'test',
                               dict(harness.DEFAULT_PREFS))
        self.p._started = True
        self.p.mqtt_connected = True

    def test_loop_survives_exception_in_timed_updates(self):
        self.p.max_sleeps = 2
        with mock.patch.object(self.p, '_refresh_ha_info'), \
                mock.patch.object(self.p, '_check_timed_updates',
                                  side_effect=[AttributeError('boom'), None]) as check:
            with self.assertRaises(harness.StopLoop):
                self.p.runConcurrentThread()
        self.assertEqual(check.call_count, 2)

    def test_register_tolerates_concurrent_additions(self):
        self.p._ha_devices = {str(i): object() for i in range(3)}

        def register(_device):
            self.p._ha_devices[f'new-{len(self.p._ha_devices)}'] = object()

        with mock.patch.object(self.p, '_register_ha_device', side_effect=register) as reg:
            self.p._register_ha_devices()
        self.assertEqual(reg.call_count, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
