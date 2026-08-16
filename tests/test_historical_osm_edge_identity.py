from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "compare_historical_osm_snapshots.py"
SPEC = spec_from_file_location("ws25_007", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUILD_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_portmore_road_graph.py"
BUILD_SPEC = spec_from_file_location("ws25_007_build", BUILD_SCRIPT)
assert BUILD_SPEC and BUILD_SPEC.loader
BUILD_MODULE = module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD_MODULE)


def test_edge_identifier_is_a_stable_sha256_of_the_versioned_seed() -> None:
    assert (
        MODULE.edge_identifier(
            "3b63cd223a3a1ff958e29a44f7e39daa143d2be6660f92515086c11e4cb9f846",
            22882833,
            47,
            282378221,
            246043939,
            0,
            "forward",
        )
        == "6f56cdbed6acf00fa7efac28d44788d4d1eea58dfdcbfbb298bfd477019ab7be"
    )


def test_oneway_contract() -> None:
    assert MODULE.oneway({"oneway": "yes"}) == 1
    assert MODULE.oneway({"oneway": "-1"}) == -1
    assert MODULE.oneway({}) == 0
    assert MODULE.oneway({"junction": "roundabout"}) == 1


def test_access_precedence_and_unknown_assumption() -> None:
    assert MODULE.access_decision({"access": "no", "motor_vehicle": "yes"})[0] == "included"
    assert MODULE.access_decision({"vehicle": "private"})[0] == "excluded"
    assert MODULE.access_decision({})[:2] == ("included", "unknown_default")


def test_conditional_track_and_excluded_classes() -> None:
    assert MODULE.highway_decision({"highway": "track", "motor_vehicle": "yes"})[0]
    assert not MODULE.highway_decision({"highway": "track"})[0]
    assert not MODULE.highway_decision({"highway": "footway"})[0]


def test_target_date_temporal_support() -> None:
    assert BUILD_MODULE.temporal_support("2020-10-05T00:00:00Z")[0] == "event_supported"
    assert BUILD_MODULE.temporal_support("2020-10-06T00:00:00Z")[0] == "post_event_uncertain"
