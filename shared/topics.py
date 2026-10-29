"""MQTT topic conventions for Project 01."""
import re
from .config import load_config, validate_namespace


def validate_device_id(device_id: str) -> str:
    if not isinstance(device_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", device_id) is None:
        raise ValueError("device_id must contain only ASCII letters, digits, underscores or hyphens")
    return device_id


def telemetry_topic(device_id: str, namespace: str | None = None) -> str:
    validate_device_id(device_id)
    namespace = load_config().namespace if namespace is None else validate_namespace(namespace)
    topic = f"{namespace}/project01/devices/{device_id}/telemetry"
    if len(topic.encode('utf-8')) > 65535:
        raise ValueError("telemetry topic exceeds MQTT's 65535-byte limit")
    return topic


def subscriber_topic(namespace: str | None = None) -> str:
    namespace = load_config().namespace if namespace is None else validate_namespace(namespace)
    topic = f"{namespace}/project01/devices/+/telemetry"
    if len(topic.encode('utf-8')) > 65535:
        raise ValueError("subscriber topic exceeds MQTT's 65535-byte limit")
    return topic
