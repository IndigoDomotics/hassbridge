"""Test harness: load HassBridge modules outside Indigo with a stub `indigo` module.

Kept dependency-free beyond the plugin's own requirements.txt.
"""
import importlib
import importlib.util
import logging
import os
import sys
import types
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PLUGIN = os.path.join(ROOT, 'HassBridge.indigoPlugin', 'Contents', 'Server Plugin')


class StopLoop(Exception):
    """Raised by the stub PluginBase.sleep() to end runConcurrentThread in tests."""


def install_indigo_stub():
    indigo = types.ModuleType('indigo')

    class PluginBase:
        class StopThread(Exception):
            pass

        def __init__(self, plugin_id, display_name, version, prefs):
            self.pluginId = plugin_id
            self.pluginPrefs = prefs
            self.logger = logging.getLogger('hassbridge.test')
            self.sleep_calls = 0
            self.max_sleeps = 1

        def __del__(self):
            pass

        def sleep(self, seconds):
            self.sleep_calls += 1
            if self.sleep_calls >= self.max_sleeps:
                raise StopLoop()

    indigo.PluginBase = PluginBase
    indigo.Dict = dict
    indigo.devices = {}
    indigo.variables = {}
    for name in ('device', 'dimmer', 'relay', 'iodevice', 'speedcontrol', 'sensor',
                 'variable', 'server', 'insteon', 'zwave', 'actionGroup'):
        setattr(indigo, name, mock.MagicMock(name=f'indigo.{name}'))
    sys.modules['indigo'] = indigo
    return indigo


def load():
    """Return (indigo_stub, hassbridge_pkg, plugin_module)."""
    indigo = install_indigo_stub()
    for name in [m for m in sys.modules if m == 'hassbridge' or m.startswith(
            ('hassbridge.', 'hass_devices', 'insteon', 'variables', 'virtual', 'zwave'))]:
        del sys.modules[name]
    if SERVER_PLUGIN not in sys.path:
        sys.path.insert(0, SERVER_PLUGIN)
    spec = importlib.util.spec_from_file_location(
        'hassbridge', os.path.join(SERVER_PLUGIN, '__init__.py'),
        submodule_search_locations=[SERVER_PLUGIN])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules['hassbridge'] = pkg
    spec.loader.exec_module(pkg)
    cwd = os.getcwd()
    os.chdir(SERVER_PLUGIN)
    try:
        plugin = importlib.import_module('hassbridge.plugin')
    finally:
        os.chdir(cwd)
    return indigo, pkg, plugin


DEFAULT_PREFS = {
    'mqtt_server': '127.0.0.1',
    'mqtt_port': '1883',
    'server_url': 'http://127.0.0.1:8123',
    'access_token': '',
}
