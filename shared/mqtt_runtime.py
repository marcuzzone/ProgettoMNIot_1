"""Small Paho VERSION2 lifecycle wrapper for local MQTT test programs."""
import logging
import threading
import time
from uuid import uuid4
import paho.mqtt.client as mqtt

LOG = logging.getLogger(__name__)
CONNECT_TIMEOUT = 10.0
PUBLISH_TIMEOUT = 5.0
RECOVERY_TIMEOUT = 30.0


class MQTTConnection:
    def __init__(self, config, role, *, topic=None, message_handler=None):
        self.config = config
        self.topic = topic
        self.message_handler = message_handler
        self.ready = threading.Event()
        self.failed = threading.Event()
        self.error = None
        self.pending_since = time.monotonic()
        self.subscription_mid = None
        self.stopping = False
        self.started = False
        self.client_id = f'{role}-{uuid4().hex[:16]}'
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=self.client_id, protocol=mqtt.MQTTv311,
                                  clean_session=True, reconnect_on_failure=topic is not None)
        self.client.connect_timeout = CONNECT_TIMEOUT
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.enable_logger(LOG)
        for name in ('on_connect', 'on_connect_fail', 'on_disconnect', 'on_subscribe', 'on_message'):
            setattr(self.client, name, self._guard(getattr(self, name)))

    def _guard(self, callback):
        def guarded(*args):
            try:
                callback(*args)
            except Exception:
                LOG.exception('Unexpected MQTT callback failure')
                self.fail('MQTT callback failed; see traceback above')
        return guarded

    def fail(self, message):
        self.error = message
        self.failed.set()
        LOG.error('%s', message)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.fail(f'Broker rejected connection: {reason_code}')
            return
        LOG.info('Connected: client=%s broker=%s:%s', self.client_id,
                 self.config.broker_host, self.config.broker_port)
        if self.topic is None:
            self.ready.set()
        else:
            self.ready.clear()
            self.pending_since = time.monotonic()
            rc, self.subscription_mid = client.subscribe(self.topic, qos=0)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                self.fail(f'Subscribe request failed: {mqtt.error_string(rc)}')
            else:
                LOG.info('Subscription requested: topic=%s mid=%s', self.topic, self.subscription_mid)

    def on_connect_fail(self, client, userdata):
        LOG.warning('TCP connection failed; check DEI VPN, routing, host and port')
        if self.topic is None:
            self.fail('Publisher connection failed')

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        if mid != self.subscription_mid:
            self.fail('Unexpected subscription acknowledgment ID')
        elif not reason_code_list or any(code.is_failure for code in reason_code_list):
            self.fail('Broker rejected subscription; check topic access permissions')
        else:
            LOG.info('Subscription acknowledged: topic=%s mid=%s granted=%s',
                     self.topic, mid, ', '.join(str(code) for code in reason_code_list))
            self.ready.set()

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self.ready.clear()
        self.pending_since = time.monotonic()
        if self.stopping:
            LOG.info('Disconnected cleanly: %s', reason_code)
        elif self.topic is None:
            self.fail(f'Publisher connection lost: {reason_code}; no messages buffered or retried')
        else:
            LOG.warning('Disconnected: %s; reconnecting for at most %.0f seconds',
                        reason_code, RECOVERY_TIMEOUT)

    def on_message(self, client, userdata, message):
        if self.message_handler is not None:
            self.message_handler(message)

    def start(self):
        LOG.info('Connecting: client=%s broker=%s:%s', self.client_id,
                 self.config.broker_host, self.config.broker_port)
        self.pending_since = time.monotonic()
        self.client.connect_async(self.config.broker_host, self.config.broker_port,
                                  self.config.keepalive)
        rc = self.client.loop_start()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f'Cannot start MQTT network loop: {mqtt.error_string(rc)}')
        self.started = True
        deadline = time.monotonic() + CONNECT_TIMEOUT
        while not self.ready.wait(0.1):
            self.check()
            if time.monotonic() >= deadline:
                raise TimeoutError('MQTT connection/SUBACK timed out; check DEI VPN, broker and permissions')
        self.check()

    def check(self):
        if self.failed.is_set():
            raise RuntimeError(self.error)
        if self.topic is not None and not self.ready.is_set():
            if time.monotonic() - self.pending_since >= RECOVERY_TIMEOUT:
                raise TimeoutError('MQTT recovery/SUBACK timed out; check VPN, broker and subscription permissions')

    def close(self):
        self.stopping = True
        try:
            self.client.disconnect()
        finally:
            if self.started:
                self.client.loop_stop()
