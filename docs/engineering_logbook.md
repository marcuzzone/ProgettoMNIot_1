# Engineering logbook

Record development activities, engineering decisions and reasons, failures, debugging, testing evidence, and AI usage. Keep entries chronological. Do not include secrets.

## 2026-10-28 — Initial project structure

**Activity:** created the initial scaffold for Project 01, Smart Environment Monitoring with Network Failure and Recovery Analysis.

**Starting state:** the workspace contained the Git repository, root `.gitignore`, `.venv`, empty `prova.py`, and `RMIC-PL-Project-01_v2026_27-v03.pdf`. None of the requested packages or documentation files existed. The existing virtual environment reports Python 3.14.6.

**Changes:** added `publishers`, `subscribers`, and `shared` as packages with documentation-only `__init__.py` files; added `tests` and `examples` with `.gitkeep` placeholders; added requirements, an environment template, README, architecture notes, and MQTT design placeholder. Appended missing root ignore rules while retaining existing content.

**Decisions:** keep responsibilities separate and avoid implementing runtime behavior before the MQTT design is defined. Pin Paho MQTT 2.1.0 and python-dotenv 1.2.4 for repeatable initial dependency selection. Use the requested broker defaults and an explicit namespace placeholder. Cloud dependencies are deferred until integration design.

**Failures and debugging:** no application failure was investigated in this scaffold step. Workspace writes require approval because the session filesystem is read-only; this is an environment restriction.

**Verification scope:** check requested paths and template values, inspect the Git diff and ignore behavior, and compare hashes of preserved files and Git configuration. No dependencies are installed, no network connection to the broker is attempted, and no runtime integration tests are available. Record any later verification failures and fixes in a new entry.

**AI usage / prompt reference:** OpenAI Codex was used to inspect the workspace and prepare the initial scaffold. Reference: the user prompt in this Codex conversation dated 2026-10-28, beginning “I am developing Project 01” and containing “Task: Create the initial project structure”, with ten numbered requirements. Its constraints require preserving existing files, `.venv/.gitignore`, and Git configuration; adding only structure and documentation; keeping credentials out of the repository; and making no commits or pushes. Generated content should be reviewed by the project author.

## Entry template

- Date and objective:
- Activities and files changed:
- Engineering decisions and rationale:
- Failures or unexpected behavior:
- Debugging steps and resolution:
- Tests or checks, results, and limitations:
- AI tool, prompt reference, output used, and human review:
- Next steps:

## 2026-10-28 — Scaffold verification

All 11 new scaffold files and the five environment defaults were checked. SHA-256 hashes confirm that prova.py, the project PDF, .venv/.gitignore, and .git/config are unchanged. Initial ignore checks exposed the original root .gitignore UTF-16 encoding: appending UTF-8 rules produced mixed encoding. Converted the root file to UTF-8 while preserving its original rules, then rechecked every required exclusion. No runtime tests or dependency installation were performed.

## 2026-10-28 — Phase 5: MQTT topics and telemetry model

**Activity:** implemented shared/config.py, shared/topics.py and shared/payload.py; added a synthetic telemetry example and three unittest modules; updated MQTT design and README. Existing .env, .env.example, requirements and unrelated project files were preserved.

**Decisions:** use explicit python-dotenv loading with environment overrides and no value disclosure in errors; enforce one ASCII namespace level and consistent device IDs; require all schema v1 fields, null unavailable measurements, finite numeric values, UUID session identity and non-negative sequences/timestamps. Reject unknown and duplicate JSON fields to detect mistakes. Provide a local TelemetrySession helper that creates one UUID per execution and increments the sequence after successful message creation. A stateless validator cannot enforce ordering across messages; future receivers need per-session state.

**AI tool and prompt:** OpenAI Codex. User prompt reference: this conversation dated 2026-10-28, beginning “We are implementing Phase 5 of RMIC Project 01: MQTT Topic Design and JSON Telemetry Model.” The implementation instruction was “Please implement the shared configuration, MQTT topic conventions, and telemetry JSON schema.” The prompt specifies the exact `tagliavini/project01/devices/<device_id>/telemetry` hierarchy, namespace loaded from MQTT_NAMESPACE, required metadata and eleven nullable measurements, configuration and topic validation, JSON creation/serialization/deserialization, session UUID and sequence semantics, standard unittest tests, a JSON example, and documentation of design and AI use. It prohibits broker connections, publisher/subscriber implementation, InfluxDB/Grafana integration, Raspberry Pi installation, unrelated edits, commits and pushes. It requests a full test run, file list, JSON example, exact topics and repeatable PowerShell test command. Codex output used: these modules, tests, example, and documentation. Project author review remains pending.

**Failures and debugging:** the execution sandbox denied access to the workspace and started commands at the drive root; stopped the unintended file enumeration and used approved elevated commands with an explicit project path. No project files were changed by enumeration. No application test failures occurred.

**Verification:** the complete offline unittest discovery suite passed all 20 tests. Coverage includes all required fields, numeric/bool distinctions, invalid UUIDs, sequences and timestamps, null measurements, JSON string/bytes round trips, malformed UTF-8/JSON, unknown and duplicate fields, configuration validation and overrides, malformed device IDs, topic limits, and session UUID reuse with increasing sequence. The synthetic example also passes schema validation. Tests ran with the existing .venv Python 3.14.6, not Python 3.12; code uses Python 3.12-compatible syntax, but execution on 3.12 remains unverified. No dependency installation or external connection was performed.

**Repeat command:** `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`

**Next steps:** review the contract, then implement publishers/subscribers in a later phase with provenance-aware collectors and receiver ordering checks.

**Final configuration check:** local topic generation revealed that `.env` still contained `REPLACE_WITH_DEI_EMAIL_USERNAME`, although `.env.example` already used `tagliavini`. Updated only the local MQTT_NAMESPACE setting to the explicitly requested username and rechecked the generated topics. Other local configuration values were preserved; `.env` remains ignored by Git.

## 2026-10-28 — Phase 6: local synthetic MQTT clients

**Implemented:** publishers/test_publisher.py and subscribers/test_subscriber.py, a small shared/mqtt_runtime.py lifecycle wrapper, offline tests/test_mqtt_clients.py, and updated README/MQTT design. Existing shared/config.py, shared/topics.py and shared/payload.py were reused unchanged. No configuration, dependencies or unrelated files were changed in this phase.

**Choices:** explicitly use Paho MQTT Callback API VERSION2, MQTT 3.1.1, unique role-prefixed client IDs and clean sessions. Read connection settings and namespace from the shared configuration; require MQTT_QOS=0 for this phase. Publisher defaults to laptop_01, five messages and two seconds between samples, with retain=False. Use one TelemetrySession per execution, timestamp samples when created, and generate realistic synthetic values with a consistent 2.4 GHz channel/frequency pair. Link quality uses a documented synthetic 0–100 scale based on signal. The example IP is a documentation-only address and the BSSID is synthetic. There is no real acquisition.

**Lifecycle:** asynchronous connection with network thread and a 10-second initial connection/SUBACK deadline; socket connection timeout 10 seconds; local send wait 5 seconds. Publisher has no reconnect/retry or application buffer and exits on loss. Subscriber reconnects with 1–5 second backoff and a 30-second recovery/SUBACK deadline; subscriptions are requested in on_connect. Validate every received payload and verify topic/device correspondence, add UTC reception diagnostics, log malformed messages and continue. Callback exceptions are logged with tracebacks and surfaced to the main thread; other unexpected exceptions also get tracebacks. finally blocks disconnect and stop the loop, including Ctrl+C/error paths. Shutdown may additionally wait for an in-progress socket attempt. OS DNS resolution for non-numeric alternative hosts is outside the socket timeout; the university broker is a numeric IP.

**Delivery semantics:** log LOCAL SEND only after Paho reports local send completion. QoS 0 has no broker PUBACK or subscriber receipt acknowledgment. Verify actual delivery using matching device/session/sequence values in subscriber logs. No retained messages, Last Will, Raspberry Pi installation, InfluxDB, Grafana or professor shared topic are used. No commits or pushes.

**Actual checks:** full offline unittest suite: 33 tests passed (20 existing plus 13 new). New tests cover synthetic ranges/schema/frequency consistency, simulated provenance, per-session UUID/sequence and timestamps, CLI validation/defaults/multiple IDs, persistent publisher connection, QoS and retain flags, failed publication and timeouts with cleanup, VERSION2/MQTT 3.1.1 selection, unique IDs, subscription recreation/SUBACK failure, connection/recovery deadlines, unexpected callback reporting, and subscriber decoding/UTC diagnostics/topic mismatch. Publisher --help also executed successfully. Existing .venv is Python 3.14.6; execution on requested Python 3.12 is still unverified. No test failures or dependency installation problems occurred. No live MQTT broker connection or end-to-end exchange was attempted in this phase; successful delivery is not claimed.

**Planned manual test:** connect DEI VPN; start subscriber and wait for subscription acknowledgment and Ready; run publisher for laptop_01 with count 5 and interval 2; compare the same session UUID and sequences 0–4 in both terminals. Repeat for rpi_01 and virtual_01 without changing subscription. Confirm Ctrl+C cleanup. If messages are missing, check VPN/TCP reachability, .env and process overrides, CONNACK/SUBACK logs, namespace and subscription timing. Deliberate VPN interruption/recovery is a later manual test; QoS 0 losses are expected and are not replayed. Record actual observed results in a later entry.

**AI assistance:** OpenAI Codex implemented code, tests and docs. It inspected the installed Paho API and official Eclipse Paho client documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html . Human review and manual end-to-end verification remain pending. The complete user prompt supplied as an attachment is preserved below.

### Phase 6 AI prompt (verbatim)

```text
We are implementing Phase 6 of RMIC Project 01: the first end-to-end MQTT communication test.

The project is developed on Windows 11 using VS Code, Python 3.12, and Paho MQTT 2.x.

The shared modules for configuration, MQTT topics, and JSON telemetry have already been implemented in Phase 5.

My DEI MQTT namespace is **tagliavini**.

The university MQTT broker is:

- Host: `10.6.1.10`
- Port: `1883`
- Protocol: MQTT 3.1.1

We will use the DEI VPN to access the broker.

## Objective

Implement a publisher and subscriber that run locally on Windows 11 and communicate through the university MQTT broker.

Use Paho MQTT 2.x with Callback API VERSION2.

Reuse the existing shared configuration, topic, and payload modules.

## 1. Implement publishers/test_publisher.py

The program must:

- Run using `python -m publishers.test_publisher`.
- Read broker settings and namespace from `.env`.
- Connect to `10.6.1.10:1883`.
- Use the topic `tagliavini/project01/devices/<device_id>/telemetry`, constructed dynamically through the existing topic helper.
- Generate realistic but synthetic Wi-Fi and environmental measurements.
- Set `wifi_source` and `environment_source` to `"simulated"`.
- Use the JSON telemetry model implemented in Phase 5.
- Generate one UUID session_id per execution.
- Generate sequential message numbers starting at 0.
- Generate a new timestamp at measurement time.
- Publish five messages by default, with a two-second interval.
- Use QoS 0 and retain=False by default.
- Support CLI arguments `--device-id`, `--count`, and `--interval`.
- Use one persistent MQTT connection for the entire execution.
- Wait until the MQTT broker confirms a successful connection before publishing.
- Handle timeouts and connection errors gracefully.
- Print readable diagnostic information for every message.
- Disconnect cleanly when the execution finishes.

Use a unique MQTT client ID to avoid collisions with other clients.

The publisher must distinguish between successful local publication and confirmed delivery to a subscriber. With QoS 0, do not claim guaranteed delivery.

## 2. Implement subscribers/test_subscriber.py

The program must:

- Run using `python -m subscribers.test_subscriber`.
- Read broker settings and namespace from `.env`.
- Connect to `10.6.1.10:1883`.
- Subscribe to `tagliavini/project01/devices/+/telemetry`, constructed dynamically.
- Use Paho MQTT Callback API VERSION2.
- Subscribe within the on_connect callback so subscriptions are recreated after reconnection.
- Log successful subscription acknowledgment.
- Continuously receive messages until Ctrl+C.
- Decode each incoming message.
- Validate JSON payloads using the existing shared validation functions.
- Print the topic, device_id, session_id, sequence, timestamp, RSSI, ping, temperature, and humidity.
- Add a UTC reception timestamp to the diagnostic output.
- Handle invalid JSON and malformed payloads without crashing.
- Report connection and disconnection events.
- Disconnect cleanly on Ctrl+C.

The subscriber must have a different client ID from the publisher.

## 3. Multi-device support

The publisher must accept device IDs such as:

- laptop_01
- rpi_01
- virtual_01

All messages must be published under my personal namespace `tagliavini`.

Do not publish to the professor's shared testing topic `/rmic/wifi/metrics`.

The subscriber must be able to receive data from different device IDs without changing its subscription.

## 4. Reliability and error handling

- Use MQTT QoS 0 for this first test.
- Do not use retained messages yet.
- Do not implement Last Will yet.
- Do not implement message buffering yet.
- Handle failed broker connections with clear error messages.
- Use reasonable connection and publication timeouts.
- Prevent the program from hanging indefinitely when the broker cannot be reached.
- Avoid silently discarding unexpected exceptions.

## 5. Documentation and tests

Update the README with exact Windows PowerShell execution commands.

Update the engineering logbook with:

- Implementation choices.
- The AI prompt used.
- The planned MQTT tests.
- Expected behavior.
- Any problems actually encountered.

Add simple automated tests for synthetic telemetry generation.

All automated unit tests must work without requiring access to the university MQTT broker.

Do not claim the end-to-end MQTT test succeeded unless it was actually executed and verified.

## 6. Constraints

- Do not install software on the Raspberry Pi.
- Do not implement real Wi-Fi acquisition yet.
- Do not implement InfluxDB or Grafana integration.
- Do not hardcode MQTT credentials or other secrets.
- Do not overwrite existing shared modules unnecessarily.
- Do not create Git commits or push to GitHub automatically.

## 7. Final verification

After writing the code:

1. Show the files created or modified.
2. Run all local unit tests.
3. Provide the exact PowerShell command to start the subscriber.
4. Provide the exact PowerShell command to start the publisher.
5. Explain the expected terminal output.
6. Explain how to diagnose connection failures, subscription errors, and missing messages.
```
