"""Publish synthetic telemetry: python -m publishers.test_publisher."""
import argparse
import logging
import math
import random
import socket
import time
import paho.mqtt.client as mqtt
from shared.config import load_config
from shared.mqtt_runtime import MQTTConnection, PUBLISH_TIMEOUT
from shared.payload import TelemetrySession, serialize_payload
from shared.topics import telemetry_topic, validate_device_id

LOG = logging.getLogger(__name__)


def synthetic_measurements(rng=None):
    """Synthetic values only; never inspect local Wi-Fi or environmental sensors."""
    rng = random if rng is None else rng
    channel = rng.choice((1, 6, 11))
    signal = rng.randint(-78, -40)
    return dict(ssid='RMIC-Simulated', bssid='02:00:00:00:00:01',
                freq_mhz=2407 + 5 * channel, channel=channel, signal_dbm=signal,
                tx_bitrate_mbps=round(rng.uniform(24, 144), 1),
                link_quality=round((signal + 100) / 60 * 100, 1),
                ping_ms=round(rng.uniform(5, 45), 2), ip_addr='192.0.2.10',
                temperature=round(rng.uniform(19, 27), 2),
                humidity=round(rng.uniform(35, 65), 2))


def positive_count(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('count must be a positive integer')
    return number


def positive_interval(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('interval must be finite and greater than zero')
    return number


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--device-id', default='laptop_01', type=validate_device_id)
    result.add_argument('--count', default=5, type=positive_count)
    result.add_argument('--interval', default=2.0, type=positive_interval, help='seconds between samples')
    return result


def run(args):
    config = load_config()
    if config.qos != 0:
        raise ValueError('Phase 6 requires MQTT_QOS=0')
    topic = telemetry_topic(args.device_id, config.namespace)
    session = TelemetrySession(device_id=args.device_id, hostname=socket.gethostname(),
                               wifi_source='simulated', environment_source='simulated')
    connection = MQTTConnection(config, 'pub')
    try:
        connection.start()
        for index in range(args.count):
            connection.check()
            if not connection.client.is_connected():
                raise ConnectionError('MQTT connection lost before publication')
            payload = session.create_message(**synthetic_measurements())
            info = connection.client.publish(topic, serialize_payload(payload), qos=0, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f'Local publication failed: {mqtt.error_string(info.rc)}')
            info.wait_for_publish(timeout=PUBLISH_TIMEOUT)
            if not info.is_published():
                raise TimeoutError('Local publication timed out; delivery is unknown')
            connection.check()
            LOG.info('LOCAL SEND topic=%s device=%s session=%s sequence=%s timestamp=%.3f '
                     'RSSI=%s dBm ping=%s ms temperature=%s C humidity=%s%% mid=%s; '
                     'QoS 0: subscriber delivery unconfirmed', topic, payload['device_id'],
                     payload['session_id'], payload['sequence'], payload['timestamp'],
                     payload['signal_dbm'], payload['ping_ms'], payload['temperature'],
                     payload['humidity'], info.mid)
            if index + 1 < args.count:
                deadline = time.monotonic() + args.interval
                while time.monotonic() < deadline:
                    connection.check()
                    time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    finally:
        connection.close()


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args)
        return 0
    except KeyboardInterrupt:
        LOG.info('Publisher stopped by user')
        return 130
    except (ValueError, OSError, RuntimeError) as exc:
        LOG.error('%s', exc)
        return 1
    except Exception:
        LOG.exception('Unexpected publisher failure')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
