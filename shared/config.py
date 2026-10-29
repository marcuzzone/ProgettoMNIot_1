"""Validated, explicit loading of local MQTT settings; no network side effects."""
from dataclasses import dataclass
from pathlib import Path
import os
import re
from dotenv import dotenv_values


class ConfigError(ValueError):
    """Missing or invalid MQTT configuration."""


def validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str) or re.fullmatch(r"[A-Za-z0-9_-]+", namespace) is None:
        raise ConfigError("MQTT_NAMESPACE must contain only ASCII letters, digits, underscores or hyphens")
    return namespace


@dataclass(frozen=True)
class MQTTConfig:
    broker_host: str
    broker_port: int
    namespace: str
    qos: int
    keepalive: int

    def __post_init__(self):
        if not isinstance(self.broker_host, str) or not self.broker_host or any(c.isspace() for c in self.broker_host) or any(c in self.broker_host for c in '/\\\x00'):
            raise ConfigError("MQTT_BROKER_HOST must be a non-empty hostname or IP address without whitespace or slashes")
        validate_namespace(self.namespace)
        for field, value, low, high in (
            ("MQTT_BROKER_PORT", self.broker_port, 1, 65535),
            ("MQTT_QOS", self.qos, 0, 2),
            ("MQTT_KEEPALIVE", self.keepalive, 1, 65535),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ConfigError(f"{field} must be an integer between {low} and {high}")


def load_config(env_path: str | Path | None = None) -> MQTTConfig:
    """Read project .env (independent of cwd); process environment takes precedence.

    Every supported setting is required. Never include setting values in errors.
    """
    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[1] / ".env"
    values = {**dotenv_values(path, interpolate=False), **os.environ}
    keys = ("MQTT_BROKER_HOST", "MQTT_BROKER_PORT", "MQTT_NAMESPACE", "MQTT_QOS", "MQTT_KEEPALIVE")
    for key in keys:
        if values.get(key) is None or values[key] == "":
            raise ConfigError(f"{key} is required")
    numbers = []
    for key in (keys[1], keys[3], keys[4]):
        if re.fullmatch(r"[0-9]+", values[key]) is None:
            raise ConfigError(f"{key} must be an integer")
        try:
            numbers.append(int(values[key]))
        except ValueError:
            raise ConfigError(f"{key} must be an integer") from None
    return MQTTConfig(values[keys[0]], numbers[0], values[keys[2]], numbers[1], numbers[2])
