"""Entities become unavailable when a data section they read is missing (an endpoint that keeps failing)."""
from types import SimpleNamespace

import pytest

from _stubs import data, make_entry


def descriptions():
    from deeper_connect.binary_sensor import BINARY_SENSORS
    from deeper_connect.sensor import SENSORS
    from deeper_connect.switch import SWITCHES
    return [("sensor", d) for d in SENSORS] + [("binary", d) for d in BINARY_SENSORS] + [("switch", d) for d in SWITCHES]


def build(kind, desc, d):
    from deeper_connect.bases import DeeperBinary, DeeperSensor, DeeperSwitch
    coord = SimpleNamespace(data=d, last_update_success=True, async_add_listener=lambda *a, **k: (lambda: None),
                            config_entry=SimpleNamespace(data={"host": "x"}))
    return {"sensor": DeeperSensor, "binary": DeeperBinary, "switch": DeeperSwitch}[kind](coord, "e1", desc)


IDS = [f"{k}:{d.key}" for k, d in descriptions()]


@pytest.mark.parametrize("kind,desc", descriptions(), ids=IDS)
def test_required_sections_exist_in_the_captured_data(kind, desc):
    """Guards against a typo in `requires` (it would make the entity permanently unavailable)."""
    assert set(desc.requires) <= set(data()), f"{desc.key} requires unknown section(s) {desc.requires}"
    assert build(kind, desc, data()).available is True


@pytest.mark.parametrize("kind,desc", [(k, d) for k, d in descriptions() if d.requires], ids=[
    f"{k}:{d.key}" for k, d in descriptions() if d.requires])
def test_entity_is_unavailable_while_its_section_is_missing(kind, desc):
    for section in desc.requires:
        assert build(kind, desc, {**data(), section: None}).available is False, f"{desc.key} without {section}"


def test_derived_entities_stay_available_with_partial_data():
    """Health and the tunnel counts are computed from whatever is there, so one failing endpoint must not blank them."""
    for kind, desc in descriptions():
        if desc.key in ("health", "health_problem", "tunnel_problem", "tunnel_count"):
            assert build(kind, desc, {**data(), "usage": None, "hardware": None}).available is True, desc.key


def test_every_core_sensor_that_reads_a_section_declares_it():
    """Evaluate each description against data with ONE section removed: if the value changes, `requires` must name it."""
    derived = {"health"}  # computed from whatever is available (it even reads firmware data); deliberately has no requires
    for kind, desc in descriptions():
        if kind != "sensor" or desc.key in derived:
            continue
        full = desc.value_fn(data())
        for section in set(data()) - {"tunnels"}:
            if desc.value_fn({**data(), section: None}) != full:
                assert section in desc.requires, f"sensor {desc.key} reads '{section}' but does not declare it in requires"


def test_selects_and_time_require_their_sections():
    from deeper_connect.features.dpn import NodeSelectionSelect, RoutingModeSelect
    from deeper_connect.features.system import RebootTime
    entry = make_entry(())
    for cls, section in ((RoutingModeSelect, "dpn"), (NodeSelectionSelect, "lb"), (RebootTime, "autoreboot")):
        coord = entry.runtime_data
        coord.data = data()
        assert cls(coord, "e1").available is True
        coord.data = {**data(), section: None}
        assert cls(coord, "e1").available is False, cls.__name__
