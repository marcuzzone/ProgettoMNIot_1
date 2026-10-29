"""Strict telemetry v1 validation and session-local message creation."""
import json
import math
import time
from uuid import UUID, uuid4
from .topics import validate_device_id

SCHEMA_VERSION = 1
STRING_MEASUREMENTS = ("ssid", "bssid", "ip_addr")
INTEGER_MEASUREMENTS = ("freq_mhz", "channel")
NUMBER_MEASUREMENTS = ("signal_dbm", "tx_bitrate_mbps", "link_quality", "ping_ms", "temperature", "humidity")
MEASUREMENTS = STRING_MEASUREMENTS + INTEGER_MEASUREMENTS + NUMBER_MEASUREMENTS
METADATA = ("schema_version", "device_id", "session_id", "sequence", "timestamp", "hostname", "wifi_source", "environment_source")


class PayloadError(ValueError):
    """Telemetry does not satisfy schema version 1."""


def _number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise PayloadError("telemetry must be a JSON object")
    for field in METADATA + MEASUREMENTS:
        if field not in payload:
            raise PayloadError(f"missing required field: {field}")
    if set(payload) != set(METADATA + MEASUREMENTS):
        raise PayloadError("unknown fields are not supported in schema version 1")
    if type(payload['schema_version']) is not int or payload['schema_version'] != SCHEMA_VERSION:
        raise PayloadError("schema_version must be integer 1")
    try:
        validate_device_id(payload['device_id'])
    except ValueError as exc:
        raise PayloadError(str(exc)) from None
    session = payload['session_id']
    try:
        if not isinstance(session, str) or str(UUID(session)) != session.lower():
            raise ValueError
    except (ValueError, AttributeError):
        raise PayloadError("session_id must be a hyphenated UUID string") from None
    if type(payload['sequence']) is not int or payload['sequence'] < 0:
        raise PayloadError("sequence must be a non-negative integer")
    if not _number(payload['timestamp']) or payload['timestamp'] < 0:
        raise PayloadError("timestamp must be finite, non-negative Unix seconds")
    if not isinstance(payload['hostname'], str):
        raise PayloadError("hostname must be a string")
    for field in ('wifi_source', 'environment_source'):
        if payload[field] not in ('measured', 'simulated'):
            raise PayloadError(f"{field} must be measured or simulated")
    for field in MEASUREMENTS:
        value = payload[field]
        if value is None:
            continue
        valid = (isinstance(value, str) if field in STRING_MEASUREMENTS else
                 type(value) is int if field in INTEGER_MEASUREMENTS else _number(value))
        if not valid:
            expected = 'string' if field in STRING_MEASUREMENTS else 'integer' if field in INTEGER_MEASUREMENTS else 'finite number'
            raise PayloadError(f"{field} must be {expected} or null")
    return payload


def create_telemetry(*, device_id: str, session_id: str, sequence: int,
                     hostname: str, wifi_source: str, environment_source: str,
                     timestamp: int | float | None = None, **measurements) -> dict:
    """Caller supplies a session UUID reused across messages; unavailable values default to None."""
    if set(measurements) - set(MEASUREMENTS):
        raise PayloadError("unknown measurement field")
    payload = dict(schema_version=SCHEMA_VERSION, device_id=device_id, session_id=session_id,
                   sequence=sequence, timestamp=time.time() if timestamp is None else timestamp,
                   hostname=hostname, wifi_source=wifi_source, environment_source=environment_source)
    payload.update(dict.fromkeys(MEASUREMENTS))
    payload.update(measurements)
    return validate_payload(payload)


def serialize_payload(payload: dict) -> str:
    return json.dumps(validate_payload(payload), allow_nan=False, ensure_ascii=True)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PayloadError("duplicate JSON field")
        result[key] = value
    return result


def deserialize_payload(data: str | bytes) -> dict:
    if not isinstance(data, (str, bytes)):
        raise PayloadError("JSON input must be a string or UTF-8 bytes")
    try:
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        payload = json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise PayloadError("invalid JSON: expected UTF-8 JSON with unique fields") from None
    return validate_payload(payload)


class TelemetrySession:
    """Create once per publisher execution. Single-threaded, in-memory sequence state.

    Sequence starts at zero and advances only after successful message validation.
    """
    def __init__(self, *, device_id: str, hostname: str, wifi_source: str, environment_source: str):
        self._metadata = dict(device_id=device_id, hostname=hostname, wifi_source=wifi_source,
                              environment_source=environment_source, session_id=str(uuid4()))
        self._sequence = 0
        create_telemetry(**self._metadata, sequence=0, timestamp=0)

    @property
    def session_id(self):
        return self._metadata['session_id']

    def create_message(self, *, timestamp=None, **measurements):
        payload = create_telemetry(**self._metadata, sequence=self._sequence,
                                   timestamp=timestamp, **measurements)
        self._sequence += 1
        return payload
