import json
from pathlib import Path
import unittest
from shared.payload import (MEASUREMENTS, METADATA, PayloadError, TelemetrySession,
                            create_telemetry, deserialize_payload, serialize_payload, validate_payload)


class PayloadTests(unittest.TestCase):
    def message(self, **changes):
        payload = create_telemetry(device_id='rpi_01', session_id='12345678-1234-4234-8234-123456789abc',
                                   sequence=0, timestamp=1793145600.5, hostname='test-host',
                                   wifi_source='measured', environment_source='simulated',
                                   signal_dbm=-61.5, freq_mhz=2412, temperature=22.4)
        return {**payload, **changes}

    def test_roundtrip(self):
        payload = self.message()
        encoded = serialize_payload(payload)
        self.assertEqual(deserialize_payload(encoded), payload)
        self.assertEqual(deserialize_payload(encoded.encode('utf-8')), payload)
        self.assertIsInstance(json.loads(encoded)['temperature'], float)

    def test_all_fields_and_null_measurements(self):
        payload = self.message(**dict.fromkeys(MEASUREMENTS))
        self.assertEqual(set(payload), set(METADATA + MEASUREMENTS))
        self.assertEqual(deserialize_payload(serialize_payload(payload)), payload)

    def test_every_field_required(self):
        for field in METADATA + MEASUREMENTS:
            payload = self.message()
            del payload[field]
            with self.subTest(field=field), self.assertRaisesRegex(PayloadError, field):
                validate_payload(payload)

    def test_invalid_metadata(self):
        cases = {'schema_version': [True, '1', 2, 1.0], 'device_id': ['bad/id', None],
                 'session_id': ['bad', 42, '12345678123442348234123456789abc'],
                 'sequence': [-1, 1.2, True, '0'],
                 'timestamp': [-1, True, '123', None, float('inf'), float('nan')],
                 'hostname': [None, 42], 'wifi_source': ['unknown', None, []],
                 'environment_source': ['unknown', 1]}
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaisesRegex(PayloadError, field):
                    validate_payload(self.message(**{field: value}))

    def test_invalid_measurement_types(self):
        for field in MEASUREMENTS:
            for value in (True, [], {}):
                with self.subTest(field=field), self.assertRaisesRegex(PayloadError, field):
                    validate_payload(self.message(**{field: value}))
        for field in ('signal_dbm', 'temperature', 'freq_mhz', 'channel'):
            with self.assertRaises(PayloadError):
                validate_payload(self.message(**{field: '12'}))
        for field in ('freq_mhz', 'channel'):
            with self.assertRaises(PayloadError):
                validate_payload(self.message(**{field: 1.5}))
        for value in (float('inf'), float('nan')):
            with self.assertRaises(PayloadError):
                serialize_payload(self.message(temperature=value))

    def test_invalid_json(self):
        for value in ('{', '[]', 'null', '42', b'\xff', '{"a":1,"a":2}', 123):
            with self.subTest(value=value), self.assertRaises(PayloadError):
                deserialize_payload(value)

    def test_unknown_fields(self):
        with self.assertRaises(PayloadError):
            validate_payload(self.message(extra=1))
        with self.assertRaises(PayloadError):
            create_telemetry(device_id='rpi_01', session_id=self.message()['session_id'], sequence=0,
                             hostname='test', wifi_source='measured', environment_source='measured', typo=1)

    def test_session_identity_and_sequence(self):
        args = dict(device_id='rpi_01', hostname='host', wifi_source='measured', environment_source='simulated')
        session = TelemetrySession(**args)
        first = session.create_message(timestamp=0)
        with self.assertRaises(PayloadError):
            session.create_message(temperature='bad')
        second = session.create_message()
        self.assertEqual((first['sequence'], second['sequence']), (0, 1))
        self.assertEqual(first['session_id'], second['session_id'])
        self.assertNotEqual(session.session_id, TelemetrySession(**args).session_id)
        self.assertGreater(second['timestamp'], 0)

    def test_example(self):
        path = Path(__file__).resolve().parents[1] / 'examples' / 'telemetry_example.json'
        validate_payload(deserialize_payload(path.read_text(encoding='utf-8')))
