"""Require all app containers to run the exact release before migration."""
import argparse
import json
import sys

SERVICES = {"backend", "frontend", "websocket", "scheduler", "queue-short", "queue-long"}


def verify(containers, release):
    seen = set()
    for container in containers:
        service = container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service")
        if service not in SERVICES or service in seen:
            raise ValueError("unexpected or duplicate app service")
        seen.add(service)
        if not container.get("State", {}).get("Running"):
            raise ValueError(f"{service} is not running")
        mounts = {mount["Destination"]: mount["Source"] for mount in container["Mounts"]}
        for destination, source in {
            "/home/frappe/frappe-bench/apps/hrms": release,
            "/home/frappe/frappe-bench/assets/hrms": release + "/hrms/public",
        }.items():
            if mounts.get(destination) != source:
                raise ValueError(f"{service} has incorrect release mounts")
    if seen != SERVICES:
        raise ValueError("missing app services")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    args = parser.parse_args()
    verify(json.load(sys.stdin), args.release)
    print("Exact release mounts verified for all six app services")
