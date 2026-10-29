# MQTT topic and JSON design

Phase 5 implements shared configuration, topic helpers, and telemetry schema version 1. Phase 6 adds synthetic publisher and subscriber clients; see README for execution and verification.

## Configuration

`shared.config.load_config()` reads the project-root `.env` using python-dotenv, independent of the working directory. Existing process environment variables override file values. An explicit file path can be supplied for tests. Loading does not mutate the process environment; interpolation is disabled. All five settings are required:

| Setting | Validation |
| --- | --- |
| MQTT_BROKER_HOST | Non-empty hostname or IP address, without whitespace, slashes or NUL; no DNS lookup |
| MQTT_BROKER_PORT | Integer 1–65535 |
| MQTT_NAMESPACE | One non-empty level matching `[A-Za-z0-9_-]+` |
| MQTT_QOS | Integer 0, 1 or 2 |
| MQTT_KEEPALIVE | Integer 1–65535 seconds (project policy requires a positive keepalive) |

Errors identify the setting and rule without displaying its value. Configuration is loaded explicitly, never on module import. No namespace is hardcoded in Python source. The current `.env.example` namespace is `tagliavini`.

## Topics

The exact hierarchy is `<MQTT_NAMESPACE>/project01/devices/<device_id>/telemetry`.

With the configured namespace:

- `tagliavini/project01/devices/rpi_01/telemetry`
- `tagliavini/project01/devices/laptop_01/telemetry`
- `tagliavini/project01/devices/virtual_01/telemetry`
- Subscriber filter: `tagliavini/project01/devices/+/telemetry`

`telemetry_topic(device_id)` and `subscriber_topic()` load the configured namespace; an explicit namespace argument supports reuse and isolated tests. IDs and namespaces use ASCII letters, digits, underscores and hyphens, preserving case. Empty values, spaces, slashes, MQTT wildcards and all other characters are rejected. Generated topics must fit the MQTT 65535-byte limit. The subscriber's single-level `+` matches one device ID.

## JSON schema version 1

Every field below must be present. Measurements default to JSON `null` when unavailable; metadata cannot be null. Numbers are JSON numbers, never quoted strings. Python booleans are rejected as numbers. NaN and infinities are rejected.

| Field | Type | Meaning / units |
| --- | --- | --- |
| schema_version | integer, exactly 1 | Schema contract |
| device_id | string | Same validated ID used in the topic |
| session_id | hyphenated UUID string | Identifies one publisher execution |
| sequence | non-negative integer | Starts at 0; increases within a session |
| timestamp | finite non-negative number | Unix seconds since UTC epoch, fractional seconds allowed |
| hostname | string | Origin machine name |
| wifi_source | measured or simulated | Provenance of Wi-Fi data |
| environment_source | measured or simulated | Provenance of environmental data |
| ssid | string or null | Wi-Fi network name |
| bssid | string or null | Access point identifier |
| freq_mhz | integer or null | Frequency in MHz |
| channel | integer or null | Wi-Fi channel |
| signal_dbm | number or null | Signal strength in dBm |
| tx_bitrate_mbps | number or null | Transmit bitrate in Mbps |
| link_quality | number or null | Native collector quality scale; collectors must document the scale before comparison |
| ping_ms | number or null | Ping latency in milliseconds |
| ip_addr | string or null | Device IP address |
| temperature | number or null | Temperature in degrees Celsius |
| humidity | number or null | Relative humidity in percent |

Version 1 rejects missing or unknown fields, unsupported schema versions, invalid UUIDs, invalid IDs and incorrect types. Measurement physical ranges and string formats beyond the specified types are not constrained yet. Duplicate JSON keys, malformed JSON and invalid UTF-8 are rejected. The example in `examples/telemetry_example.json` is synthetic.

## Shared API and session lifecycle

`create_telemetry(...)` requires the caller to supply `session_id` and `sequence`; it fills all absent measurement fields with null and defaults the timestamp to `time.time()`. `validate_payload`, `serialize_payload` and `deserialize_payload` validate the complete contract; deserialization accepts strings or UTF-8 bytes.

Future publisher code should create one `TelemetrySession` per execution and call `create_message()` for each sample. The helper generates its UUID once, starts the sequence at zero, and advances only after successful validation. It has single-threaded, in-memory state. Stateless validation cannot detect out-of-order or repeated messages: a future receiver can track `(device_id, session_id, sequence)` and compare the payload ID to the MQTT topic. Retransmission should reuse the original message identity.

```python
from shared.payload import TelemetrySession, serialize_payload
from shared.topics import telemetry_topic

session = TelemetrySession(device_id="rpi_01", hostname="raspberrypi",
                           wifi_source="simulated", environment_source="simulated")
message = session.create_message(temperature=22.4, humidity=48.2)
json_text = serialize_payload(message)
topic = telemetry_topic(message["device_id"])
```

This example only creates local data. Phase 6 clients use MQTT 3.1.1, Callback API VERSION2, QoS 0, clean sessions, and non-retained publications. The publisher aborts on connection loss; the subscriber reconnects and resubscribes with a bounded recovery wait. Last Will, buffering, duplicate handling, and failure experiments remain future work. QoS 0 does not replay samples lost during outages.

## Offline verification and AI assistance

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Tests use temporary .env files and mocks; no external services are contacted. Codex assisted implementation, tests, and documentation; see the engineering logbook for the prompt reference and verification evidence.

