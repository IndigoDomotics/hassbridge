"""MQTT disconnect/reconnect regression tests.

Failures corrected:
1. paho invokes on_disconnect(client, userdata, rc); the plugin defined
   on_mqtt_disconnect(self), so every broker disconnect raised TypeError inside
   the paho network loop, mqtt_connected stayed True and the plugin never reconnected.
2. runConcurrentThread started a new connect every minute while a previous
   connect was still in progress.
3. paho-mqtt 2.0.0 requires callback_api_version; mqtt.Client(...) without it
   raised TypeError at plugin start.

Run: python -m unittest discover -s tests   (with requirements.txt installed)
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402


class MqttReconnect(unittest.TestCase):
    def setUp(self):
        self.indigo, self.pkg, self.plugin_mod = harness.load()
        self.p = self.plugin_mod.Plugin('com.github.wonderslug.hassbridge', 'HassBridge',
                                        'test', dict(harness.DEFAULT_PREFS))

    def test_client_constructs_with_installed_paho(self):
        self.assertIsNotNone(self.p.mqtt_client)

    def test_disconnect_callback_accepts_paho_v1_signature(self):
        self.p.mqtt_connected = True
        self.p.mqtt_client.on_disconnect(self.p.mqtt_client, None, 7)
        self.assertFalse(self.p.mqtt_connected)

    def test_no_new_connect_while_connect_in_progress(self):
        self.p._started = True
        self.p.mqtt_connected = False
        self.p.mqtt_connecting = True
        with mock.patch.object(self.p, '_connect_to_mqtt_broker') as connect, \
                mock.patch.object(self.p, '_refresh_ha_info'), \
                mock.patch.object(self.p, '_check_timed_updates'):
            with self.assertRaises(harness.StopLoop):
                self.p.runConcurrentThread()
        connect.assert_not_called()

    def test_reconnect_rebuilds_client_with_callbacks(self):
        new_client = mock.MagicMock(name='new paho client')
        with mock.patch.object(self.p, '_setup_mqtt_client', return_value=new_client):
            self.p.mqtt_connected = False
            self.p.mqtt_connecting = False
            self.p._connect_to_mqtt_broker()
        self.assertIs(self.p.mqtt_client, new_client)
        self.assertEqual(new_client.on_disconnect, self.p.on_mqtt_disconnect)
        self.assertEqual(new_client.on_connect, self.p.on_mqtt_connect)
        new_client.connect.assert_called_once()
        self.assertTrue(self.p.mqtt_connecting)
        self.p.on_mqtt_connect(new_client, None, {}, 0)
        self.assertTrue(self.p.mqtt_connected)
        self.assertFalse(self.p.mqtt_connecting)

    def test_failed_connack_clears_connecting(self):
        self.p.mqtt_connecting = True
        self.p.on_mqtt_connect(self.p.mqtt_client, None, {}, 5)
        self.assertFalse(self.p.mqtt_connecting)
        self.assertFalse(self.p.mqtt_connected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
