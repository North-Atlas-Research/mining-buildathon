from pathlib import Path

import yaml


def test_region_config_records_frozen_ws25_003_decision():
    config_path = Path(__file__).resolve().parents[1] / "configs" / "regions" / "portmore_2020.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["region_id"] == "portmore_jamaica_2020"
    assert config["boundary"]["status"] == "accepted_operational_study_boundary"
    assert config["boundary"]["canonical_path"] == "Processed/region/portmore_boundary.gpkg"
    assert config["boundary"]["legal_authority_flag"] is False
    assert config["boundary"]["boundary_edge_review_distance_m"] == 750
    assert config["boundary"]["acquisition_context_buffer_m"] == 2000
    edge_review = config["boundary"]["derived_geometries"]["boundary_edge_review"]
    assert edge_review["geometry_semantics"] == "two_sided_band_around_boundary_line"
    assert edge_review["usage"] == "boundary_edge_review_only"
    assert edge_review["operational_inclusion_polygon"] is False
    assert config["crs"]["source_representation_crs"].endswith("EPSG:3857")
    assert config["crs"]["original_source_crs"] == "unknown"
    assert config["crs"]["analysis_crs"] == "EPSG:3448"
    assert config["crs"]["decision_status"] == "frozen"


def test_region_config_records_ws25_004_shelter_contract():
    config_path = Path(__file__).resolve().parents[1] / "configs/regions/portmore_2020.yaml"
    shelters = yaml.safe_load(config_path.read_text(encoding="utf-8"))["shelters"]
    assert shelters["source_year"] == 2019
    assert shelters["expected_record_count"] == 20
    assert shelters["canonical_storage_crs"] == "EPSG:3448"
    assert shelters["shelter_id_contract"] == "uuid5_from_immutable_source_record_id"
    assert shelters["source_capacity_unit"] == "not_established"
    assert shelters["operational_usable_capacity_default"] is None
    assert shelters["unresolved_geometry_policy"] == (
        "explicit_null_with_unknown_spatial_classification"
    )
    assert shelters["boundary_classification_semantics"] == (
        "mvp_operational_not_legal_determination"
    )
