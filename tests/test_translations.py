"""Entity names come from translations; English must stay identical to what earlier releases showed, and every
language file must have the same keys and placeholders as English."""
import json
import pathlib
import re

import pytest

from _stubs import ALL, collect_entities, domain_of, leaves, with_platform as _with_platform

PKG = pathlib.Path(__file__).parent.parent / "custom_components" / "deeper_connect"
TRANSLATIONS = PKG / "translations"
GOLDEN = json.loads((pathlib.Path(__file__).parent / "fixtures" / "entity_names.json").read_text())


def load(path):
    return json.loads(pathlib.Path(path).read_text())


def with_platform(entity, language="en"):
    return _with_platform(entity, language)


def all_entities():
    return collect_entities(ALL, {"geo_lookup": True})


def test_strings_json_matches_english_translation():
    assert load(PKG / "strings.json") == load(TRANSLATIONS / "en.json")


def test_english_names_are_identical_to_the_previous_release():
    ents = all_entities()
    assert {e.unique_id for e in ents} == set(GOLDEN)
    for e in ents:
        assert with_platform(e).name == GOLDEN[e.unique_id], e.unique_id


def test_every_entity_is_named_by_a_translation_key():
    for e in all_entities():
        assert e.translation_key, f"{e.unique_id} has no translation_key"
        assert not hasattr(e, "_attr_name"), f"{e.unique_id} sets _attr_name, which would bypass translations"


def test_no_unused_or_missing_entity_name_translations():
    en = load(TRANSLATIONS / "en.json")["entity"]
    defined = {(p, k) for p, keys in en.items() for k, node in keys.items() if "name" in node}
    used = {(domain_of(e), e.translation_key) for e in all_entities()}
    assert used - defined == set(), f"entity name translations missing: {sorted(used - defined)}"
    assert defined - used == set(), f"entity name translations nothing uses: {sorted(defined - used)}"


def test_descriptions_have_no_hardcoded_names():
    from deeper_connect.binary_sensor import BINARY_SENSORS
    from deeper_connect.sensor import SENSORS
    from deeper_connect.switch import SWITCHES
    from homeassistant.helpers.entity import UNDEFINED
    for d in (*SENSORS, *BINARY_SENSORS, *SWITCHES):
        assert d.name is UNDEFINED, f"{d.key} still has a hard-coded name"


def test_dynamic_names_use_placeholders():
    by_uid = {e.unique_id: with_platform(e) for e in all_entities()}
    assert by_uid["e1_app_hboMax"].name == "App Hbo Max relocation"
    assert by_uid["e1_client_aa:bb:cc:00:00:03_route"].name == "Client Blocked TV route mode"
    assert by_uid["e1_client_aa:bb:cc:00:00:03_blackholed"].name == "Client Blocked TV blackholed"


def test_unknown_client_is_named_by_its_mac():
    from _stubs import make_entry
    from deeper_connect.features.access_control import ClientRouteMode
    e = with_platform(ClientRouteMode(make_entry(ALL).runtime_data, "e1", "ff:ff:ff:ff:ff:ff"))
    assert e.name == "Client ff:ff:ff:ff:ff:ff route mode"


# ---- language files ----
LANGS = sorted(p.stem for p in TRANSLATIONS.glob("*.json"))


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text)) if isinstance(text, str) else set()


def test_polish_translation_exists():
    assert "pl" in LANGS


@pytest.mark.parametrize("lang", [l for l in LANGS if l != "en"])
def test_language_has_exactly_the_keys_of_english(lang):
    en = dict(leaves(load(TRANSLATIONS / "en.json")))
    other = dict(leaves(load(TRANSLATIONS / f"{lang}.json")))
    assert set(en) - set(other) == set(), f"{lang}: missing {sorted(set(en) - set(other))[:8]}"
    assert set(other) - set(en) == set(), f"{lang}: extra {sorted(set(other) - set(en))[:8]}"
    for key, text in en.items():
        assert placeholders(other[key]) == placeholders(text), f"{lang}: placeholders differ in {key}: {other[key]!r}"
        assert other[key].strip(), f"{lang}: empty text for {key}"


@pytest.mark.parametrize("lang", [l for l in LANGS if l != "en"])
def test_language_resolves_every_entity_name(lang):
    for e in all_entities():
        name = with_platform(e, lang).name
        assert name and "{" not in name, f"{lang}: {e.unique_id} -> {name!r}"


def test_client_entity_name_follows_a_rename_in_the_deeper_app():
    """The name used to be computed on every read; HA caches it now, so a rename must be pushed through explicitly."""
    from _stubs import make_entry
    from deeper_connect.features.access_control import ClientBlackholed, ClientRouteMode
    entry = make_entry(ALL)
    coord = entry.runtime_data
    for cls, suffix in ((ClientRouteMode, "route mode"), (ClientBlackholed, "blackholed")):
        e = with_platform(cls(coord, "e1", "aa:bb:cc:00:00:03"))
        e.async_write_ha_state = lambda: None
        assert e.name == f"Client Blocked TV {suffix}"
        source = next(c for s in ("online", "offline") for c in coord.data["clients"].get(s) or []
                      if str(c.get("mac")).lower() == "aa:bb:cc:00:00:03")  # all_clients() returns copies
        source["remark"] = "Renamed TV"  # `remark` is what client_title prefers
        e._handle_coordinator_update()
        assert e.name == f"Client Renamed TV {suffix}", e.name
        source["remark"] = "Blocked TV"
