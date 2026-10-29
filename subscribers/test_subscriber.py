"""Receive validated telemetry: python -m subscribers.test_subscriber."""
from datetime import datetime, timezone
import logging
import time
from shared.config import load_config
from shared.mqtt_runtime import MQTTConnection
from shared.payload import PayloadError, deserialize_payload
from shared.topics import subscriber_topic, telemetry_topic

LOG = logging.getLogger(__name__)


def display_message(message, namespace):
    received_at = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    try:
        payload = deserialize_payload(message.payload)
        if message.topic != telemetry_topic(payload['device_id'], namespace):
            raise PayloadError('topic does not match payload device_id or configured namespace')
    except (PayloadError, ValueError) as exc:
        LOG.warning('INVALID received_utc=%s topic=%s: %s', received_at, message.topic, exc)
        return
    LOG.info('RECEIVED received_utc=%s topic=%s device_id=%s session_id=%s sequence=%s '
             'timestamp=%s RSSI=%s dBm ping=%s ms temperature=%s C humidity=%s%%',
             received_at, message.topic, payload['device_id'], payload['session_id'],
             payload['sequence'], payload['timestamp'], payload['signal_dbm'],
             payload['ping_ms'], payload['temperature'], payload['humidity'])


def run():
    config = load_config()
    if config.qos != 0:
        raise ValueError('Phase 6 requires MQTT_QOS=0')
    connection = MQTTConnection(config, 'sub', topic=subscriber_topic(config.namespace),
                                message_handler=lambda message: display_message(message, config.namespace))
    try:
        connection.start()
        LOG.info('Ready; waiting for telemetry. Press Ctrl+C to stop.')
        while True:
            connection.check()
            time.sleep(0.1)
    finally:
        connection.close()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        run()
        return 0
    except KeyboardInterrupt:
        LOG.info('Subscriber stopped by user')
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        LOG.error('%s', exc)
        return 1
    except Exception:
        LOG.exception('Unexpected subscriber failure')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
