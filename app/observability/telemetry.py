"""Azure Monitor OpenTelemetry setup."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_azure_monitor_telemetry() -> None:
    """Enable Azure Monitor OpenTelemetry when a connection string is configured."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.info(
            "azure_monitor_telemetry_disabled",
            extra={"event": "azure_monitor_telemetry_disabled"},
        )
        return

    # Microsoft's current Python Azure Monitor distro exposes configure_azure_monitor
    # as the setup entry point and accepts connection_string as a keyword argument.
    # Docs:
    # https://learn.microsoft.com/en-us/python/api/azure-monitor-opentelemetry/azure.monitor.opentelemetry
    # https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-configuration
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=connection_string)
    logger.info(
        "azure_monitor_telemetry_enabled",
        extra={"event": "azure_monitor_telemetry_enabled"},
    )
