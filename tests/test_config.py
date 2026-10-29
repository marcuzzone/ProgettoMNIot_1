import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from shared.config import ConfigError, MQTTConfig, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '.env'
        self.values = dict(MQTT_BROKER_HOST='localhost', MQTT_BROKER_PORT='1883',
                           MQTT_NAMESPACE='test_user', MQTT_QOS='0', MQTT_KEEPALIVE='60')
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def load(self, values):
        self.path.write_text('\n'.join(f'{k}={v}' for k, v in values.items()), encoding='utf-8')
        return load_config(self.path)

    def test_valid_file(self):
        self.assertEqual(self.load(self.values), MQTTConfig('localhost', 1883, 'test_user', 0, 60))

    def test_environment_precedence(self):
        with patch.dict(os.environ, MQTT_NAMESPACE='override'):
            self.assertEqual(self.load(self.values).namespace, 'override')

    def test_every_setting_required(self):
        for key in self.values:
            for missing in (True, False):
                with self.subTest(key=key, missing=missing):
                    values = self.values.copy()
                    if missing:
                        del values[key]
                    else:
                        values[key] = ''
                    with self.assertRaisesRegex(ConfigError, key):
                        self.load(values)

    def test_invalid_values_and_safe_errors(self):
        cases = {'MQTT_BROKER_HOST': ['bad host', 'bad/host'],
                 'MQTT_BROKER_PORT': ['0', '65536', 'abc', '1.5', '-1'],
                 'MQTT_QOS': ['3', '-1', 'true'], 'MQTT_KEEPALIVE': ['0', '65536'],
                 'MQTT_NAMESPACE': ['bad/name', 'bad+name', 'bad name', '#', 'café']}
        for key, invalid in cases.items():
            for value in invalid:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ConfigError) as caught:
                        self.load({**self.values, key: value})
                    self.assertIn(key, str(caught.exception))
                    self.assertNotIn(value, str(caught.exception))

    def test_missing_file(self):
        with self.assertRaisesRegex(ConfigError, 'MQTT_BROKER_HOST'):
            load_config(self.path)

    def test_direct_config_rejects_bool(self):
        with self.assertRaises(ConfigError):
            MQTTConfig('localhost', True, 'test', 0, 60)
