# Project 01: Smart Environment Monitoring with Network Failure and Recovery Analysis

Mobile Networks and IoT course project. The goal is to collect environmental measurements and study how network failures affect delivery and recovery.

Phase 5 adds validated shared configuration, MQTT topic helpers, telemetry schema version 1, a JSON example, and offline unit tests. Phase 6 adds local synthetic MQTT publisher and subscriber entry points. Database access and dashboards are not implemented.

## Preliminary architecture

IoT device → university Mosquitto MQTT broker → Python subscriber → InfluxDB Cloud → Grafana Cloud

- `publishers/`: local synthetic test publisher; real device acquisition remains future work.
- `subscribers/`: validated telemetry reception; InfluxDB ingestion remains future work.
- `shared/`: configuration loading, topic conventions, telemetry validation and session helpers.
- `tests/`: offline standard-library unittest tests for configuration, topics and payloads.
- `examples/`: synthetic telemetry JSON without credentials.
- `docs/`: architecture, MQTT design, and engineering logbook.
- `prova.py` and the course PDF: existing files preserved unchanged.

See [architecture](docs/architecture.md), [MQTT design](docs/mqtt_design.md), and [engineering logbook](docs/engineering_logbook.md).

## Local installation on Windows 11

Target Python 3.12 or later and run these PowerShell commands from the project root. The existing `.venv` uses Python 3.14.6; keep it in place. If starting from a fresh clone without `.venv`, create it once using `py -m venv .venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Copy the template only if `.env` does not already exist. Check that `.env` contains `MQTT_NAMESPACE=tagliavini` for this project. Never commit passwords, tokens, or real credentials. `.env` is ignored by Git.

In VS Code, select `.venv\Scripts\python.exe` as the Python interpreter. Using the interpreter directly avoids needing to change PowerShell execution policy.

Dependencies are pinned to [Paho MQTT 2.1.0](https://pypi.org/project/paho-mqtt/2.1.0/) and [python-dotenv 1.2.4](https://pypi.org/project/python-dotenv/1.2.4/). These releases declare Python requirements compatible with Python 3.10+. The installed dependencies support the offline tests in the existing environment. Both MQTT clients explicitly use Paho Callback API VERSION2 and MQTT 3.1.1.

The configured broker is `10.6.1.10:1883`. Access requires an appropriate university network route; confirm the university's access instructions before connection testing. Initial configuration uses QoS 0 and a 60-second keepalive. Importing modules and running unit tests do not connect to the broker; running either MQTT entry point does.

## Future execution workflow

1. Review the implemented MQTT and JSON contract in `docs/mqtt_design.md`.
2. Run the offline tests, then start the subscriber and synthetic publisher as described below.
3. Verify MQTT delivery on the university network.
4. Add InfluxDB Cloud ingestion and configure credentials locally, then build Grafana Cloud dashboards.
5. Establish baseline measurements, introduce controlled network interruptions, and measure loss and recovery.
6. Record commands, observations, failures, fixes, and AI assistance in the logbook.

The synthetic publisher, subscriber, shared modules and offline tests are implemented. Raspberry Pi setup and software installation are outside this initial step.

## Phase 5 offline verification

Run the complete suite from the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

All 20 tests pass in the existing Python 3.14.6 environment; Python 3.12 execution has not yet been verified. No broker connection is required. See [the telemetry example](examples/telemetry_example.json) and [the schema and shared API](docs/mqtt_design.md). Create one `TelemetrySession` per future publisher execution to reuse the UUID and advance the sequence. Namespace selection comes from `MQTT_NAMESPACE` in `.env`, with process environment overrides. Codex assisted this phase; the engineering logbook records the prompt and validation.

## Phase 6: local MQTT test over the DEI VPN

Connect the DEI VPN first. Open two PowerShell terminals in the project root. Check `.env` contains these non-secret settings (process environment variables override them):

```dotenv
MQTT_BROKER_HOST=10.6.1.10
MQTT_BROKER_PORT=1883
MQTT_NAMESPACE=tagliavini
MQTT_QOS=0
MQTT_KEEPALIVE=60
```

Start the subscriber in terminal 1:

```powershell
.\.venv\Scripts\python.exe -m subscribers.test_subscriber
```

Wait for `Connected`, `Subscription acknowledged` for `tagliavini/project01/devices/+/telemetry`, and `Ready`. Then start the publisher in terminal 2:

```powershell
.\.venv\Scripts\python.exe -m publishers.test_publisher --device-id laptop_01 --count 5 --interval 2
```

The default device is `laptop_01`, count is five and interval is two seconds. `--count` must be a positive integer; `--interval` must be positive and finite. Other device examples:

```powershell
.\.venv\Scripts\python.exe -m publishers.test_publisher --device-id rpi_01
.\.venv\Scripts\python.exe -m publishers.test_publisher --device-id virtual_01
.\.venv\Scripts\python.exe -m publishers.test_publisher --help
```

These commands all run locally on Windows, including the `rpi_01` synthetic identity. They do not install or run anything on a Raspberry Pi. Both entry points also work with `python -m ...` when the intended virtual environment is active.

Expected publisher output: a unique `pub-...` client ID, connection confirmation, then five `LOCAL SEND` lines with one session UUID and sequences 0 through 4. Each line reports topic, sample timestamp, RSSI, ping, temperature and humidity. Both data sources are `simulated`; values are generated, not acquired from the machine. The publisher uses one connection, QoS 0, retain=False, and disconnects after the last local send. `LOCAL SEND` means Paho completed its local send processing; it does not confirm broker acceptance or subscriber delivery.

Expected subscriber output: a distinct `sub-...` client ID, connection and subscription acknowledgment, then `RECEIVED` lines with topic, device_id, session_id, sequence, sample timestamp, RSSI, ping, temperature, humidity, and `received_utc` in UTC. Match `(device_id, session_id, sequence)` across terminals to verify actual receipt. One wildcard subscription covers all three device identities. Ctrl+C closes the subscriber cleanly; it returns zero. Publisher Ctrl+C cleans up and returns 130. Other failures return a nonzero exit code.

Both clients reject MQTT_QOS values other than zero for this phase. There are no retained publications, Last Will, application message buffers, or publication retries. Publisher connection loss aborts the run. The subscriber retries connections with 1–5 second backoff, subscribes inside every successful on_connect callback, and waits for a new SUBACK. Initial connection plus acknowledgment has a 10-second deadline; recovery plus resubscription has a 30-second deadline. Local publication has a 5-second deadline. The network socket connection timeout is 10 seconds; cleanup can additionally wait for an in-progress connection attempt to finish. These bounds target the configured numeric broker address; operating-system DNS resolution for alternative hostnames can take longer.

### Diagnosis and verification

- Connection timeout/refusal: verify DEI VPN and university routing, `.env` host/port, process `MQTT_*` overrides, and firewall rules. A TCP check can help:

  ```powershell
  Test-NetConnection -ComputerName 10.6.1.10 -Port 1883
  Get-ChildItem Env:MQTT_*
  ```

  A successful TCP test only establishes reachability, not MQTT authorization. A rejected CONNACK reports the broker reason. Ask the course administrator about permissions if necessary; credentials are not embedded in these clients.
- Subscription error: look for a failed subscribe request, rejected SUBACK or acknowledgment timeout. Confirm the namespace and wildcard topic, and check broker access permissions. A successful connection alone does not establish a subscription.
- Missing messages: start publishing only after the subscriber prints `Ready`; compare broker addresses, namespace, device/session/sequence and both terminal logs. Non-retained QoS 0 messages published before subscription or during outages are not replayed. A local send is not evidence of receipt. `INVALID` lines identify malformed payloads or a topic/device mismatch; these are logged without stopping reception.
- Reconnection: disconnect/reconnect the VPN only as a deliberate later test. Expect disconnection logs and a new subscription acknowledgment if recovery completes before the deadline. Messages lost during the gap are not buffered or replayed.

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Phase 6 result: all 33 tests pass with the existing Python 3.14.6 virtual environment. Python 3.12 execution remains unverified. The new tests mock MQTT clients and exercise synthetic telemetry, session sequencing, CLI validation, QoS/retain flags, timeout cleanup, callback error reporting, subscription acknowledgments, and received-message validation. No live university-broker exchange was executed during implementation, so end-to-end delivery remains unverified.

Paho lifecycle behavior follows the [official client documentation](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html). Codex assisted the implementation and documentation; the engineering logbook records the supplied prompt and actual checks.
