"""VPS provider abstraction and demo implementation."""

from __future__ import annotations

import abc
import logging
import random
import uuid

log = logging.getLogger(__name__)

# Maps plan tier_key → VPS resource specs
PLAN_SPECS: dict[str, dict] = {
    "starter": {"cpu_cores": 1, "ram_mb": 1024, "disk_gb": 20, "os_template": "ubuntu-22.04"},
    "professional": {
        "cpu_cores": 2,
        "ram_mb": 4096,
        "disk_gb": 80,
        "os_template": "ubuntu-22.04",
    },
    "enterprise": {
        "cpu_cores": 4,
        "ram_mb": 8192,
        "disk_gb": 200,
        "os_template": "ubuntu-22.04",
    },
}


class VPSProvider(abc.ABC):
    """Abstract interface for VPS infrastructure providers."""

    @abc.abstractmethod
    def provision(self, job) -> dict:
        """Provision a new VPS.

        Returns:
            {"external_id": str, "ip_address": str, "vmid": int}
        """

    @abc.abstractmethod
    def start(self, instance) -> bool:
        """Start a stopped VPS instance."""

    @abc.abstractmethod
    def stop(self, instance) -> bool:
        """Gracefully stop a running VPS instance."""

    @abc.abstractmethod
    def restart(self, instance) -> bool:
        """Restart a running VPS instance."""

    @abc.abstractmethod
    def terminate(self, instance) -> bool:
        """Permanently destroy a VPS instance."""

    @abc.abstractmethod
    def status(self, instance) -> str:
        """Return the current status string of the VPS instance."""


class DemoProvider(VPSProvider):
    """Simulated provider for development / testing — no real infrastructure."""

    def provision(self, job) -> dict:
        external_id = str(uuid.uuid4())
        ip_address = f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}"  # noqa: S311
        vmid = random.randint(100, 999)  # noqa: S311
        log.info(
            "DemoProvider: provisioned job #%s → ext=%s ip=%s vmid=%s",
            job.pk,
            external_id,
            ip_address,
            vmid,
        )
        return {"external_id": external_id, "ip_address": ip_address, "vmid": vmid}

    def start(self, instance) -> bool:
        log.info("DemoProvider: start %s", instance.hostname)
        return True

    def stop(self, instance) -> bool:
        log.info("DemoProvider: stop %s", instance.hostname)
        return True

    def restart(self, instance) -> bool:
        log.info("DemoProvider: restart %s", instance.hostname)
        return True

    def terminate(self, instance) -> bool:
        log.info("DemoProvider: terminate %s", instance.hostname)
        return True

    def status(self, instance) -> str:
        return "running"


_PROVIDERS: dict[str, type[VPSProvider]] = {
    "demo": DemoProvider,
}


def get_provider(name: str = "demo") -> VPSProvider:
    """Factory: return a VPSProvider instance by name.

    Args:
        name: Provider key (currently only "demo" is available).

    Raises:
        ValueError: If the provider name is unknown.
    """
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown VPS provider: {name!r}")
    return cls()
