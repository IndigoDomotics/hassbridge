"""MQTT command payload decoding regression tests.

Failure corrected: under Python 3 paho delivers msg.payload as bytes. Cover and
Insteon keypad-button handlers compared that bytes value with str payload
settings ('OPEN', 'ON', ...), so commands from Home Assistant were ignored.

Run: python -m unittest discover -s tests   (with requirements.txt installed)
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402


def msg(payload, topic='indigo/test/set'):
    return types.SimpleNamespace(payload=payload, topic=topic)


class CommandPayloads(unittest.TestCase):
    def setUp(self):
        self.indigo, self.pkg, _ = harness.load()
        import hass_devices.cover as cover
        import insteon.devices as insteon_devices
        self.cover, self.insteon = cover, insteon_devices

    def fake(self, cls, **attrs):
        obj = types.SimpleNamespace(logger=mock.MagicMock(), **attrs)
        obj._decode_payload = getattr(cls, '_decode_payload', lambda payload: payload)
        return obj

    def test_cover_accepts_bytes_payload(self):
        Cover = self.cover.Cover
        dev = self.fake(Cover, id=101, payload_open='OPEN', payload_close='CLOSE', payload_stop='STOP')
        Cover.on_command_message(dev, None, None, msg(b'OPEN'))
        self.indigo.iodevice.setBinaryOutput.assert_called_once_with(101, index=0, value=True)

    def test_cover_ignores_unknown_payload(self):
        Cover = self.cover.Cover
        dev = self.fake(Cover, id=101, payload_open='OPEN', payload_close='CLOSE', payload_stop='STOP')
        Cover.on_command_message(dev, None, None, msg(b'BOGUS'))
        self.indigo.iodevice.setBinaryOutput.assert_not_called()

    def test_keypad_button_led_on_from_bytes_payload(self):
        Btn = self.insteon.InsteonKeypadButtonLight
        self.indigo.devices[7] = types.SimpleNamespace(ledStates=[False] * 8)
        dev = self.fake(Btn, parent_id=7, button=3, is_relay=False, payload_on='ON', payload_off='OFF')
        Btn.on_command_message(dev, None, None, msg(b'ON'))
        self.indigo.dimmer.setLedState.assert_called_once_with(7, index=2, value=True)

    def test_keypad_button_led_off_from_bytes_payload(self):
        Btn = self.insteon.InsteonKeypadButtonLight
        self.indigo.devices[7] = types.SimpleNamespace(ledStates=[False, False, True] + [False] * 5)
        dev = self.fake(Btn, parent_id=7, button=3, is_relay=True, payload_on='ON', payload_off='OFF')
        Btn.on_command_message(dev, None, None, msg(b'OFF'))
        self.indigo.relay.setLedState.assert_called_once_with(7, index=2, value=False)

    def test_str_payload_still_accepted(self):
        Cover = self.cover.Cover
        dev = self.fake(Cover, id=5, payload_open='OPEN', payload_close='CLOSE', payload_stop='STOP')
        Cover.on_command_message(dev, None, None, msg('CLOSE'))
        self.indigo.iodevice.setBinaryOutput.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
