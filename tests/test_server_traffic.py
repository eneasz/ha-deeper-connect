"""Shared-traffic sensors read the device's serverTraffic block (traffic from other users through this device)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "custom_components"))
from deeper_connect.sensor import CORE_SENSORS  # noqa: E402

BY_KEY = {d.key: d for d in CORE_SENSORS}


def test_server_sensors_read_server_traffic_not_client_traffic():
    data = {"traffic": {"serverTraffic": {"upload": "104.3 KB", "download": "2.0 MB"},
                        "clientTraffic": {"upload": "7.3 MB", "download": "93.9 MB"}}}
    assert BY_KEY["server_upload"].value_fn(data) == pytest.approx(104.3 * 1024, abs=1)
    assert BY_KEY["server_download"].value_fn(data) > BY_KEY["server_upload"].value_fn(data)
    assert BY_KEY["server_download"].value_fn(data) < BY_KEY["client_download"].value_fn(data)


def test_server_sensors_need_traffic_section_and_tolerate_missing_block():
    assert BY_KEY["server_upload"].requires == ("traffic",)
    assert BY_KEY["server_download"].value_fn({"traffic": {}}) is None
