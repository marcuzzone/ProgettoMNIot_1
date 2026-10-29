import unittest
from unittest.mock import patch
from shared.config import MQTTConfig
from shared.topics import telemetry_topic, subscriber_topic, validate_device_id


class TopicTests(unittest.TestCase):
    def test_topics_from_loaded_config(self):
        config = MQTTConfig('localhost', 1883, 'test_namespace', 0, 60)
        with patch('shared.topics.load_config', return_value=config):
            self.assertEqual(telemetry_topic('rpi_01'), 'test_namespace/project01/devices/rpi_01/telemetry')
            self.assertEqual(subscriber_topic(), 'test_namespace/project01/devices/+/telemetry')

    def test_explicit_namespace(self):
        for device in ('rpi_01', 'laptop_01', 'virtual_01', 'A-z_09'):
            self.assertEqual(telemetry_topic(device, 'unit'), f'unit/project01/devices/{device}/telemetry')
        self.assertEqual(subscriber_topic('unit'), 'unit/project01/devices/+/telemetry')

    def test_invalid_devices(self):
        for device in ('', '+', '#', 'a/b', 'a b', 'a.b', 'café', 'a\n', None, 12):
            with self.subTest(device=device), self.assertRaises(ValueError):
                validate_device_id(device)
            with self.assertRaises(ValueError):
                telemetry_topic(device, 'unit')

    def test_invalid_namespace(self):
        for namespace in ('', 'a/b', '+', '#', 'a b'):
            with self.assertRaises(ValueError):
                subscriber_topic(namespace)
            with self.assertRaises(ValueError):
                telemetry_topic('rpi_01', namespace)

    def test_oversized_topics(self):
        with self.assertRaises(ValueError):
            telemetry_topic('a' * 65535, 'unit')
        with self.assertRaises(ValueError):
            subscriber_topic('a' * 65535)
