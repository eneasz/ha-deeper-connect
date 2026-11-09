"""Config flow (user, reauth) and the multi-step options flow, driven directly without a Home Assistant instance."""
import asyncio
from types import SimpleNamespace

import pytest

from _stubs import data, make_entry  # noqa: F401  (also puts custom_components on sys.path)

USER = {"host": "192.0.2.10", "username": "admin", "password": "secret"}


def run(coro):
    return asyncio.run(coro)


class FakeClient:
    """Stands in for DeeperClient inside config_flow._validate."""
    exc: Exception | None = None

    def __init__(self, session, host, username, password):
        pass

    async def device_id(self):
        return "device-1"

    async def login(self):
        if FakeClient.exc:
            raise FakeClient.exc


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    import deeper_connect.config_flow as cf
    FakeClient.exc = None
    monkeypatch.setattr(cf, "DeeperClient", FakeClient)


# ---- _validate ----
def test_validate_success_returns_device_id():
    from deeper_connect.config_flow import _validate
    assert run(_validate(USER)) == ("device-1", None)


@pytest.mark.parametrize("exc,code", [("auth", "invalid_auth"), ("conn", "cannot_connect"), ("other", "unknown")])
def test_validate_maps_errors(exc, code):
    from deeper_connect.api import DeeperAuthError, DeeperConnectionError
    from deeper_connect.config_flow import _validate
    FakeClient.exc = {"auth": DeeperAuthError("x"), "conn": DeeperConnectionError("x"), "other": RuntimeError("x")}[exc]
    assert run(_validate(USER)) == (None, code)


# ---- user step ----
def _config_flow(monkeypatch, already=False):
    from homeassistant.data_entry_flow import AbortFlow
    from deeper_connect.config_flow import DeeperConfigFlow
    flow = DeeperConfigFlow()
    flow.hass = SimpleNamespace()
    flow.context = {"source": "user"}
    ids = []

    async def set_uid(uid, **kw):
        ids.append(uid)

    def abort_if_configured(**kw):
        if already:
            raise AbortFlow("already_configured")

    monkeypatch.setattr(flow, "async_set_unique_id", set_uid)
    monkeypatch.setattr(flow, "_abort_if_unique_id_configured", abort_if_configured)
    flow.seen_ids = ids
    return flow


def test_user_step_shows_form_with_defaults(monkeypatch):
    res = run(_config_flow(monkeypatch).async_step_user())
    assert res["type"].value == "form" and res["step_id"] == "user"
    defaults = {str(k): k.default() for k in res["data_schema"].schema if k.default is not None and callable(k.default)}
    assert defaults["host"] == "34.34.34.34" and defaults["username"] == "admin"


def test_user_step_creates_entry_and_sets_unique_id(monkeypatch):
    flow = _config_flow(monkeypatch)
    res = run(flow.async_step_user(USER))
    assert res["type"].value == "create_entry" and res["title"] == "Deeper 192.0.2.10"
    assert res["data"] == USER and flow.seen_ids == ["device-1"]


@pytest.mark.parametrize("exc,code", [("auth", "invalid_auth"), ("conn", "cannot_connect")])
def test_user_step_reports_errors_and_keeps_host(monkeypatch, exc, code):
    from deeper_connect.api import DeeperAuthError, DeeperConnectionError
    FakeClient.exc = {"auth": DeeperAuthError("x"), "conn": DeeperConnectionError("x")}[exc]
    res = run(_config_flow(monkeypatch).async_step_user(USER))
    assert res["type"].value == "form" and res["errors"] == {"base": code}
    host_key = next(k for k in res["data_schema"].schema if str(k) == "host")
    assert host_key.default() == "192.0.2.10"


def test_user_step_aborts_for_already_configured_device(monkeypatch):
    from homeassistant.data_entry_flow import AbortFlow
    with pytest.raises(AbortFlow):
        run(_config_flow(monkeypatch, already=True).async_step_user(USER))


# ---- reauth ----
def test_reauth_updates_password(monkeypatch):
    flow = _config_flow(monkeypatch)
    entry = SimpleNamespace(data=dict(USER))
    updated = {}
    monkeypatch.setattr(flow, "_get_reauth_entry", lambda: entry)
    monkeypatch.setattr(flow, "async_update_reload_and_abort", lambda e, data: updated.update(data=data) or {"type": "abort"})
    run(flow.async_step_reauth_confirm({"password": "new"}))
    assert updated["data"] == {**USER, "password": "new"}


def test_reauth_wrong_password_shows_error(monkeypatch):
    from deeper_connect.api import DeeperAuthError
    FakeClient.exc = DeeperAuthError("x")
    flow = _config_flow(monkeypatch)
    monkeypatch.setattr(flow, "_get_reauth_entry", lambda: SimpleNamespace(data=dict(USER)))
    res = run(flow.async_step_reauth_confirm({"password": "bad"}))
    assert res["type"].value == "form" and res["errors"] == {"base": "invalid_auth"}


# ---- reconfigure ----
def _reconfigure_flow(monkeypatch, entry_unique_id="device-1"):
    from homeassistant.data_entry_flow import AbortFlow
    flow = _config_flow(monkeypatch)
    entry = SimpleNamespace(data=dict(USER), unique_id=entry_unique_id)
    updated = {}
    monkeypatch.setattr(flow, "_get_reconfigure_entry", lambda: entry)
    monkeypatch.setattr(flow, "async_set_unique_id", lambda uid, **kw: _async(flow.seen_ids.append(uid)))

    def mismatch(reason="unique_id_mismatch", **kw):
        if entry.unique_id != flow.seen_ids[-1]:
            raise AbortFlow(reason)
    monkeypatch.setattr(flow, "_abort_if_unique_id_mismatch", mismatch)
    monkeypatch.setattr(flow, "async_update_reload_and_abort", lambda e, **kw: updated.update(kw) or {"type": "abort", **kw})
    flow.updated = updated
    return flow


async def _async(value=None):
    return value


def test_reconfigure_form_is_prefilled_and_password_is_optional(monkeypatch):
    res = run(_reconfigure_flow(monkeypatch).async_step_reconfigure())
    assert res["type"].value == "form" and res["step_id"] == "reconfigure"
    keys = {str(k): k for k in res["data_schema"].schema}
    assert keys["host"].default() == "192.0.2.10" and keys["username"].default() == "admin"
    assert type(keys["password"]).__name__ == "Optional"


def test_reconfigure_changes_host_and_keeps_saved_password_when_left_blank(monkeypatch):
    flow = _reconfigure_flow(monkeypatch)
    run(flow.async_step_reconfigure({"host": "192.0.2.99", "username": "admin"}))
    assert flow.updated["data_updates"] == {"host": "192.0.2.99", "username": "admin", "password": "secret"}


def test_reconfigure_can_change_the_password(monkeypatch):
    flow = _reconfigure_flow(monkeypatch)
    run(flow.async_step_reconfigure({"host": "192.0.2.10", "username": "admin", "password": "new"}))
    assert flow.updated["data_updates"]["password"] == "new"


def test_reconfigure_refuses_a_different_device(monkeypatch):
    from homeassistant.data_entry_flow import AbortFlow
    flow = _reconfigure_flow(monkeypatch, entry_unique_id="some-other-device")
    with pytest.raises(AbortFlow) as err:
        run(flow.async_step_reconfigure({"host": "192.0.2.99", "username": "admin"}))
    assert err.value.reason == "wrong_device" and flow.updated == {}


def test_reconfigure_adopts_the_device_id_for_an_entry_that_has_none(monkeypatch):
    flow = _reconfigure_flow(monkeypatch, entry_unique_id=None)
    run(flow.async_step_reconfigure({"host": "192.0.2.10", "username": "admin"}))
    assert flow.updated["unique_id"] == "device-1"


@pytest.mark.parametrize("exc,code", [("auth", "invalid_auth"), ("conn", "cannot_connect")])
def test_reconfigure_reports_errors_and_changes_nothing(monkeypatch, exc, code):
    from deeper_connect.api import DeeperAuthError, DeeperConnectionError
    FakeClient.exc = {"auth": DeeperAuthError("x"), "conn": DeeperConnectionError("x")}[exc]
    flow = _reconfigure_flow(monkeypatch)
    res = run(flow.async_step_reconfigure({"host": "192.0.2.99", "username": "admin", "password": "bad"}))
    assert res["type"].value == "form" and res["errors"] == {"base": code} and flow.updated == {}


# ---- DHCP discovery ----
def _dhcp_flow(monkeypatch, existing_hosts=(), already=False):
    flow = _config_flow(monkeypatch, already)
    flow._async_current_entries = lambda *a, **k: [SimpleNamespace(data={"host": h}) for h in existing_hosts]
    return flow


def _info(ip="192.0.2.77"):
    from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
    return DhcpServiceInfo(ip=ip, hostname="dcn-mini", macaddress="020000000001")


def test_manifest_matches_the_dcn_mini_hostname():
    import json, pathlib
    manifest = json.loads((pathlib.Path(__file__).parent.parent / "custom_components" / "deeper_connect" / "manifest.json").read_text())
    assert manifest["dhcp"] == [{"hostname": "dcn-mini"}]


def test_dhcp_ignores_an_address_that_is_already_configured(monkeypatch):
    res = run(_dhcp_flow(monkeypatch, existing_hosts=["192.0.2.77"]).async_step_dhcp(_info()))
    assert res["type"].value == "abort" and res["reason"] == "already_configured"


def test_dhcp_new_address_asks_for_the_login_and_names_the_card(monkeypatch):
    flow = _dhcp_flow(monkeypatch, existing_hosts=["192.0.2.10"])
    res = run(flow.async_step_dhcp(_info()))
    assert res["type"].value == "form" and res["step_id"] == "discovery_confirm"
    assert res["description_placeholders"] == {"host": "192.0.2.77"} and flow.context["title_placeholders"] == {"host": "192.0.2.77"}
    assert {str(k) for k in res["data_schema"].schema} == {"username", "password"}  # host is fixed by the discovery


def test_dhcp_confirm_creates_the_entry_for_the_discovered_host(monkeypatch):
    flow = _dhcp_flow(monkeypatch)
    run(flow.async_step_dhcp(_info()))
    res = run(flow.async_step_discovery_confirm({"username": "admin", "password": "secret"}))
    assert res["type"].value == "create_entry" and res["title"] == "Deeper 192.0.2.77"
    assert res["data"] == {"host": "192.0.2.77", "username": "admin", "password": "secret"} and flow.seen_ids == ["device-1"]


def test_dhcp_confirm_for_a_known_device_at_a_new_address_updates_its_host(monkeypatch):
    from homeassistant.data_entry_flow import AbortFlow
    flow = _dhcp_flow(monkeypatch, existing_hosts=["192.0.2.10"])
    seen = {}

    def abort_if_configured(updates=None, **kw):
        seen["updates"] = updates
        raise AbortFlow("already_configured")
    monkeypatch.setattr(flow, "_abort_if_unique_id_configured", abort_if_configured)
    run(flow.async_step_dhcp(_info()))
    with pytest.raises(AbortFlow):
        run(flow.async_step_discovery_confirm({"username": "admin", "password": "secret"}))
    assert seen["updates"] == {"host": "192.0.2.77"}


def test_dhcp_confirm_reports_a_wrong_password(monkeypatch):
    from deeper_connect.api import DeeperAuthError
    FakeClient.exc = DeeperAuthError("x")
    flow = _dhcp_flow(monkeypatch)
    run(flow.async_step_dhcp(_info()))
    res = run(flow.async_step_discovery_confirm({"username": "admin", "password": "bad"}))
    assert res["type"].value == "form" and res["errors"] == {"base": "invalid_auth"}


# ---- options flow ----
def _options_flow(monkeypatch, options=None, features=("dpn", "app_relocator", "ads_security", "system")):
    from deeper_connect.config_flow import DeeperOptionsFlow
    entry = make_entry(features, options)
    monkeypatch.setattr(DeeperOptionsFlow, "config_entry", property(lambda self: entry))
    flow = DeeperOptionsFlow()
    flow.hass = SimpleNamespace()
    flow.handler = entry.entry_id
    return flow


def _defaults(res):
    return {str(k): (k.default() if callable(k.default) else k.default) for k in res["data_schema"].schema}


def _step(flow, name, user_input=None):
    return run(getattr(flow, f"async_step_{name}")(user_input))


def test_options_init_defaults_for_entry_that_never_saved_features(monkeypatch):
    res = _step(_options_flow(monkeypatch), "init")
    d = _defaults(res)
    assert res["step_id"] == "init" and d["scan_interval"] == 60 and d["geo_lookup"] is False
    assert sorted(d["features"]) == ["ads_security", "app_relocator", "dpn", "system"]


def test_options_no_picker_steps_when_only_system_enabled(monkeypatch):
    res = _step(_options_flow(monkeypatch), "init", {"scan_interval": 30, "features": ["system"], "geo_lookup": False})
    assert res["type"].value == "create_entry"
    assert res["data"]["features"] == ["system"] and res["data"]["scan_interval"] == 30


def test_options_apps_step_defaults_to_customised_apps(monkeypatch):
    from deeper_connect.util import customised_apps
    flow = _options_flow(monkeypatch)
    res = _step(flow, "init", {"scan_interval": 60, "features": ["app_relocator"], "geo_lookup": False})
    assert res["type"].value == "form" and res["step_id"] == "apps"
    assert _defaults(res)["apps"] == customised_apps(data()["apps"])


def test_options_full_walk_apps_then_clients_then_save(monkeypatch):
    flow = _options_flow(monkeypatch)
    res = _step(flow, "init", {"scan_interval": 45, "features": ["app_relocator", "access_control"], "geo_lookup": True})
    assert res["step_id"] == "apps"
    res = _step(flow, "apps", {"apps": ["netflix"]})
    assert res["type"].value == "form" and res["step_id"] == "clients"
    res = _step(flow, "clients", {"access_clients": ["aa:bb:cc:00:00:03"]})
    assert res["type"].value == "create_entry"
    assert res["data"] == {"scan_interval": 45, "features": ["app_relocator", "access_control"], "geo_lookup": True,
                           "apps": ["netflix"], "access_clients": ["aa:bb:cc:00:00:03"], "client_control": False}


def test_options_clients_step_can_turn_on_client_control(monkeypatch):
    flow = _options_flow(monkeypatch)
    _step(flow, "init", {"scan_interval": 60, "features": ["access_control"], "geo_lookup": False})
    res = _step(flow, "clients", {"access_clients": ["aa:bb:cc:00:00:03"], "client_control": True})
    assert res["data"]["client_control"] is True


def test_options_access_control_only_goes_straight_to_clients(monkeypatch):
    flow = _options_flow(monkeypatch)
    res = _step(flow, "init", {"scan_interval": 60, "features": ["access_control"], "geo_lookup": False})
    assert res["step_id"] == "clients"


def test_options_clients_default_to_pinned(monkeypatch):
    from deeper_connect.util import pinned_clients
    flow = _options_flow(monkeypatch)
    _step(flow, "init", {"scan_interval": 60, "features": ["access_control"], "geo_lookup": False})
    res = _step(flow, "clients")
    assert sorted(_defaults(res)["access_clients"]) == sorted(pinned_clients(data()))


def test_options_keep_earlier_picks_when_a_feature_is_switched_off(monkeypatch):
    flow = _options_flow(monkeypatch, {"features": ["app_relocator"], "apps": ["netflix"], "scan_interval": 60})
    res = _step(flow, "init", {"scan_interval": 60, "features": ["system"], "geo_lookup": False})
    assert res["type"].value == "create_entry" and res["data"]["apps"] == ["netflix"]


def test_options_scan_interval_has_a_floor():
    import voluptuous as vol
    from deeper_connect.const import MIN_SCAN_INTERVAL
    from deeper_connect.config_flow import DeeperOptionsFlow
    flow = DeeperOptionsFlow()
    flow.hass = SimpleNamespace()
    flow.handler = "e1"
    entry = make_entry(())
    DeeperOptionsFlow.config_entry = property(lambda self: entry)
    try:
        schema = run(flow.async_step_init())["data_schema"]
        with pytest.raises(vol.Invalid):
            schema({"scan_interval": MIN_SCAN_INTERVAL - 1, "features": [], "geo_lookup": False})
        schema({"scan_interval": MIN_SCAN_INTERVAL, "features": [], "geo_lookup": False})
    finally:
        del DeeperOptionsFlow.config_entry  # restore the inherited property
