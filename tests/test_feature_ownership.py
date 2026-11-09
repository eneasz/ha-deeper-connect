"""Every entity a platform creates must be attributed to the feature that created it.

`features_owning()` decides which entities are removed when a feature is switched off, by looking at the unique id
alone. These tests run the real platform setup for each feature combination and check the two agree, so a new entity
(or a renamed feature) cannot silently escape clean-up.
"""
import itertools

import pytest

from _stubs import ALL, collect_entities, rest_of


def _subsets():
    for n in range(len(ALL) + 1):
        yield from itertools.combinations(ALL, n)


def test_unique_ids_are_unique_for_every_feature_set():
    for feats in _subsets():
        ids = [e.unique_id for e in collect_entities(feats, {"geo_lookup": True})]
        assert len(ids) == len(set(ids)), f"duplicate unique ids with {feats}"


@pytest.mark.parametrize("feats", list(_subsets()), ids=lambda f: "+".join(f) or "core-only")
def test_entities_never_need_a_feature_that_is_off(feats):
    """Nothing is created whose owning features are not all enabled (else clean-up would delete it on reload)."""
    from deeper_connect.features import features_owning
    for ent in collect_entities(feats, {"geo_lookup": True}):
        needs = features_owning(rest_of(ent))
        assert needs <= set(feats), f"{ent.unique_id} created with {feats} but needs {needs}"


def test_core_only_creates_no_feature_entities():
    from deeper_connect.features import features_owning
    for ent in collect_entities((), {"geo_lookup": True}):
        assert features_owning(rest_of(ent)) == set(), ent.unique_id


def test_features_add_only_their_own_entities():
    """With all features on, everything beyond the core set is attributed to some feature."""
    from deeper_connect.features import features_owning
    core = {rest_of(e) for e in collect_entities(())}
    for ent in collect_entities(ALL, {"geo_lookup": True}):
        rest = rest_of(ent)
        if rest not in core:
            assert features_owning(rest), f"{ent.unique_id} is feature-created but features_owning() says it is core"


@pytest.mark.parametrize("feature", ALL)
def test_each_feature_creates_something(feature):
    """Guards against a feature that silently creates nothing (or whose entities are mis-attributed)."""
    from deeper_connect.features import features_owning
    core = {rest_of(e) for e in collect_entities(())}
    own = [e for e in collect_entities((feature,), {"geo_lookup": True}) if rest_of(e) not in core]
    assert own, f"{feature} adds no entities"
    assert all(feature in features_owning(rest_of(e)) for e in own)


def test_geo_tracker_needs_both_option_and_dpn():
    assert not [e for e in collect_entities(("dpn",), {}) if e.unique_id.endswith("_tracker")]
    assert not [e for e in collect_entities(("system",), {"geo_lookup": True}) if e.unique_id.endswith("_tracker")]
    assert [e for e in collect_entities(("dpn",), {"geo_lookup": True}) if e.unique_id.endswith("_tracker")]
