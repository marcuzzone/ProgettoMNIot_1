"""All Phase 6 tests are offline; MQTT clients are mocked."""
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import paho.mqtt.client as mqtt
from publishers.test_publisher import parser, run, synthetic_measurements
from shared.config import MQTTConfig
from shared.mqtt_runtime import MQTTConnection
from shared.payload import TelemetrySession, deserialize_payload, serialize_payload, validate_payload
from subscribers.test_subscriber import display_message

CONFIG = MQTTConfig('localhost', 1883, 'unit_namespace', 0, 60)


class SyntheticTelemetryTests(unittest.TestCase):
    def test_realistic_schema_and_consistent_frequency(self):
        session = TelemetrySession(device_id='virtual_01', hostname='test',
                                   wifi_source='simulated', environment_source='simulated')
        rng = random.Random(42)
        with patch('shared.payload.time.time', side_effect=[1000.25, 1002.25]):
            first = session.create_message(**synthetic_measurements(rng))
            second = session.create_message(**synthetic_measurements(rng))
        for payload in (first, second):
            validate_payload(payload)
            self.assertEqual(deserialize_payload(serialize_payload(payload)), payload)
            self.assertEqual(payload['wifi_source'], 'simulated')
            self.assertEqual(payload['environment_source'], 'simulated')
            self.assertIn(payload['channel'], (1, 6, 11))
            self.assertEqual(payload['freq_mhz'], 2407 + 5 * payload['channel'])
            for key, low, high in [('signal_dbm', -78, -40), ('tx_bitrate_mbps', 24, 144),
                                   ('link_quality', 0, 100), ('ping_ms', 5, 45),
                                   ('temperature', 19, 27), ('humidity', 35, 65)]:
                self.assertGreaterEqual(payload[key], low)
                self.assertLessEqual(payload[key], high)
        self.assertEqual(first['session_id'], second['session_id'])
        self.assertEqual((first['sequence'], second['sequence']), (0, 1))
        self.assertEqual((first['timestamp'], second['timestamp']), (1000.25, 1002.25))

    def test_cli_defaults_and_multi_device(self):
        args = parser().parse_args([])
        self.assertEqual((args.device_id, args.count, args.interval), ('laptop_01', 5, 2))
        for device in ('laptop_01', 'rpi_01', 'virtual_01'):
            self.assertEqual(parser().parse_args(['--device-id', device]).device_id, device)

    def test_invalid_cli(self):
        for args in (['--device-id', 'bad/id'], ['--count', '0'], ['--count', '-2'],
                     ['--interval', '-1'], ['--interval', 'nan'], ['--interval', 'inf']):
            with self.subTest(args=args), patch('sys.stderr'), self.assertRaises(SystemExit):
                parser().parse_args(args)

    def test_publisher_single_connection_and_local_send(self):
        with patch('publishers.test_publisher.load_config', return_value=CONFIG), \
             patch('publishers.test_publisher.MQTTConnection') as factory, \
             patch('publishers.test_publisher.time.sleep'):
            connection = factory.return_value
            info = connection.client.publish.return_value
            info.rc = mqtt.MQTT_ERR_SUCCESS
            info.is_published.return_value = True
            with self.assertLogs('publishers.test_publisher', level='INFO') as logs:
                run(SimpleNamespace(device_id='laptop_01', count=2, interval=0))
            factory.assert_called_once_with(CONFIG, 'pub')
            connection.start.assert_called_once()
            connection.close.assert_called_once()
            calls = connection.client.publish.call_args_list
            self.assertEqual(len(calls), 2)
            messages = [deserialize_payload(call.args[1]) for call in calls]
            self.assertEqual([p['sequence'] for p in messages], [0, 1])
            self.assertEqual(messages[0]['session_id'], messages[1]['session_id'])
            for call in calls:
                self.assertEqual(call.args[0], 'unit_namespace/project01/devices/laptop_01/telemetry')
                self.assertEqual(call.kwargs, dict(qos=0, retain=False))
            self.assertIn('subscriber delivery unconfirmed', '\n'.join(logs.output))

    def test_publisher_failures_always_cleanup(self):
        for failure in ('connection', 'publish_rc', 'publish_timeout', 'disconnected'):
            with self.subTest(failure=failure), \
                 patch('publishers.test_publisher.load_config', return_value=CONFIG), \
                 patch('publishers.test_publisher.MQTTConnection') as factory:
                connection = factory.return_value
                info = connection.client.publish.return_value
                info.rc = mqtt.MQTT_ERR_SUCCESS
                info.is_published.return_value = True
                if failure == 'connection':
                    connection.start.side_effect = TimeoutError('timed out')
                elif failure == 'publish_rc':
                    info.rc = mqtt.MQTT_ERR_NO_CONN
                elif failure == 'publish_timeout':
                    info.is_published.return_value = False
                else:
                    connection.client.is_connected.return_value = False
                with self.assertRaises((RuntimeError, OSError)):
                    run(SimpleNamespace(device_id='rpi_01', count=1, interval=2))
                connection.close.assert_called_once()


class MQTTLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch('shared.mqtt_runtime.mqtt.Client')
        self.factory = self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client = self.factory.return_value
        self.client.loop_start.return_value = mqtt.MQTT_ERR_SUCCESS
        self.client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 7)
        self.success = SimpleNamespace(is_failure=False)
        self.rejected = SimpleNamespace(is_failure=True)

    def subscriber(self):
        return MQTTConnection(CONFIG, 'sub', topic='unit_namespace/project01/devices/+/telemetry')

    def test_version2_protocol_and_unique_ids(self):
        publisher = MQTTConnection(CONFIG, 'pub')
        subscriber = self.subscriber()
        self.assertNotEqual(publisher.client_id, subscriber.client_id)
        self.assertEqual(len(publisher.client_id), 20)
        for call in self.factory.call_args_list:
            self.assertEqual(call.kwargs['callback_api_version'], mqtt.CallbackAPIVersion.VERSION2)
            self.assertEqual(call.kwargs['protocol'], mqtt.MQTTv311)
            self.assertTrue(call.kwargs['clean_session'])
        self.assertFalse(self.factory.call_args_list[0].kwargs['reconnect_on_failure'])
        self.assertTrue(self.factory.call_args_list[1].kwargs['reconnect_on_failure'])

    def test_subscribe_on_every_connect_and_wait_for_ack(self):
        connection = self.subscriber()
        for _ in range(2):
            connection.on_connect(self.client, None, None, self.success, None)
            self.assertFalse(connection.ready.is_set())
            connection.on_subscribe(self.client, None, 7, [self.success], None)
            self.assertTrue(connection.ready.is_set())
        self.assertEqual(self.client.subscribe.call_count, 2)
        self.client.subscribe.assert_called_with(connection.topic, qos=0)

    def test_rejected_connack_and_suback(self):
        for failure in ('connack', 'suback', 'subscribe_rc', 'wrong_mid'):
            with self.subTest(failure=failure):
                connection = self.subscriber()
                with self.assertLogs('shared.mqtt_runtime', level='ERROR'):
                    if failure == 'connack':
                        connection.on_connect(self.client, None, None, self.rejected, None)
                    else:
                        if failure == 'subscribe_rc':
                            self.client.subscribe.return_value = (mqtt.MQTT_ERR_NO_CONN, 7)
                        connection.on_connect(self.client, None, None, self.success, None)
                        if failure != 'subscribe_rc':
                            connection.on_subscribe(self.client, None, 99 if failure == 'wrong_mid' else 7,
                                                    [self.rejected] if failure == 'suback' else [self.success], None)
                with self.assertRaises(RuntimeError):
                    connection.check()
                self.client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 7)

    def test_connection_timeout_and_cleanup(self):
        connection = MQTTConnection(CONFIG, 'pub')
        with patch('shared.mqtt_runtime.CONNECT_TIMEOUT', 0), \
             self.assertRaises(TimeoutError):
            connection.start()
        connection.close()
        self.client.disconnect.assert_called_once()
        self.client.loop_stop.assert_called_once()

    def test_connection_waits_for_successful_connack(self):
        connection = MQTTConnection(CONFIG, 'pub')
        self.client.loop_start.side_effect = lambda: (
            connection.on_connect(self.client, None, None, self.success, None) or mqtt.MQTT_ERR_SUCCESS)
        connection.start()
        self.assertTrue(connection.ready.is_set())
        self.client.connect_async.assert_called_once_with('localhost', 1883, 60)
        connection.close()

    def test_recovery_timeout(self):
        connection = self.subscriber()
        connection.pending_since = 0
        with patch('shared.mqtt_runtime.time.monotonic', return_value=31), self.assertRaises(TimeoutError):
            connection.check()

    def test_unexpected_callback_exception_is_reported(self):
        connection = self.subscriber()
        connection.message_handler = Mock(side_effect=RuntimeError('unexpected'))
        with self.assertLogs('shared.mqtt_runtime', level='ERROR') as logs:
            self.client.on_message(self.client, None, Mock())
        self.assertTrue(connection.failed.is_set())
        self.assertIn('Traceback', '\n'.join(logs.output))


class SubscriberDiagnosticsTests(unittest.TestCase):
    def test_valid_invalid_and_device_mismatch(self):
        session = TelemetrySession(device_id='rpi_01', hostname='host',
                                   wifi_source='simulated', environment_source='simulated')
        message = SimpleNamespace(topic='unit_namespace/project01/devices/rpi_01/telemetry',
                                  payload=serialize_payload(session.create_message()).encode())
        with self.assertLogs('subscribers.test_subscriber', level='INFO') as logs:
            display_message(message, 'unit_namespace')
        self.assertIn('received_utc=', logs.output[0])
        self.assertIn('+00:00', logs.output[0])
        self.assertIn('sequence=0', logs.output[0])
        message.topic = 'unit_namespace/project01/devices/laptop_01/telemetry'
        with self.assertLogs('subscribers.test_subscriber', level='WARNING'):
            display_message(message, 'unit_namespace')
        for invalid in (b'not json', b'\xff', b'{}'):
            message.payload = invalid
            with self.assertLogs('subscribers.test_subscriber', level='WARNING'):
                display_message(message, 'unit_namespace')
