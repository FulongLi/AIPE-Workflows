"""Unit tests for the pure mapping logic of the specialist adapters (no solver, no FreeCAD)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aipe_workflows.adapters.field_simulation import _parse_strand_diameter, window_params_from_magnetics
from aipe_workflows.adapters.pcb_agent import board_is_clean, summarise_drc, summarise_erc
from aipe_workflows.adapters.semiconductor_database import _bridge_block, _compact, _pick

FIXTURES = Path(__file__).parent / "fixtures"


def _magnetics_result() -> dict:
    return {
        "selected_core": "core.tdk-e70-33-32",
        "selected_candidate": {
            "core": "core.tdk-e70-33-32", "arrangement": "P-S-P",
            "layout": {"winding_height_m": 0.04041,
                       "layers": [{"d_in_m": 0.0016, "d_out_m": 0.00421, "section": 0, "turns": 10, "winding": "primary"},
                                  {"d_in_m": 0.00441, "d_out_m": 0.00814, "section": 1, "turns": 10, "winding": "secondary"},
                                  {"d_in_m": 0.00834, "d_out_m": 0.01095, "section": 2, "turns": 10, "winding": "primary"}]},
            "windings": {"primary": {"conductor": "litz 436 x 0.1 mm", "copper_area_m2": 3.424e-6},
                         "secondary": {"conductor": "litz 889 x 0.1 mm", "copper_area_m2": 6.982e-6}},
        },
    }


def test_strand_diameter_parsing():
    assert _parse_strand_diameter("litz 436 x 0.1 mm") == pytest.approx(1e-4)
    assert _parse_strand_diameter("foil 0.2 mm") is None


def test_window_params_from_magnetics_maps_core_and_layout():
    pytest.importorskip("aipe_magnetics")
    params, notes = window_params_from_magnetics(_magnetics_result())
    assert params["centre_leg_width_m"] == pytest.approx(0.022)
    assert params["window_width_m"] == pytest.approx(0.013)
    assert params["window_height_m"] == pytest.approx(0.0438)
    assert params["core_depth_m"] == pytest.approx(0.032)
    assert params["primary_width_m"] == pytest.approx(0.00522, rel=1e-3)
    assert params["secondary_width_m"] == pytest.approx(0.00373, rel=1e-3)
    assert params["insulation_gap_m"] == pytest.approx(0.0002, rel=1e-3)
    assert params["clearance_centre_m"] == pytest.approx(0.0016)
    assert 0.3 < params["fill_factor"] < 0.5
    assert params["strand_diameter_m"] == pytest.approx(1e-4)
    # the blocks must fit the window: centre half-leg + clearance + builds + gaps <= centre half-leg + window width
    extent = params["clearance_centre_m"] + params["primary_width_m"] + params["secondary_width_m"] + 2 * params["insulation_gap_m"]
    assert extent <= params["window_width_m"]
    assert any("catalogue record" in n for n in notes)


def test_window_params_fall_back_without_core():
    params, notes = window_params_from_magnetics({"selected_candidate": {}})
    assert params == {}
    assert "default window" in notes[0]


def _screening() -> dict:
    def item(cid, part, integration, evidence, total, complete=True):
        return {"candidate_id": f"candidate_{cid or part}", "canonical_id": cid, "part_number": part, "manufacturer": "X", "integration": integration,
                "electrical": {"vds_rating": 1200.0, "id_rating": 40.0}, "loss": {"evidence": evidence, "total": total, "complete": complete, "conduction": total, "turn_off": 0.0},
                "thermal": {"rth_junction_to_case": 0.5, "tj_max_rating": 448.15, "fixed_point": {"converged": True, "junction_temperature": 330.0, "loss": total}}}
    return {"bridges": [
        {"bridge": "primary", "worst_case_switch": "S3", "dc_bus_voltage": 799.4, "stress": {"switch_id": "S3", "current_rms": 9.4},
         "ranked": [item("mod_a", "MODULE-A", "module", "canonical_tensor", 6.9), item("disc_b", "DISC-B", "discrete", "canonical_tensor", 8.2),
                    item(None, "DISC-C", "discrete", "datasheet_point", 7.5, complete=False)], "excluded": []},
        {"bridge": "secondary", "worst_case_switch": "S8", "dc_bus_voltage": 400.0, "stress": {"switch_id": "S8", "current_rms": 19.0},
         "ranked": [item("disc_d", "DISC-D", "discrete", "canonical_tensor", 15.0)], "excluded": [{}]},
    ]}


def test_device_pick_honours_package_preference_and_canonical_records():
    s = _screening()
    primary = _bridge_block(s, "primary")["ranked"]
    assert _pick(primary, None)["canonical_id"] == "mod_a"           # database ranking kept when no preference
    assert _pick(primary, "discrete")["canonical_id"] == "disc_b"    # first discrete device with a canonical record and complete losses
    assert _pick(_bridge_block(s, "secondary")["ranked"], "module") is None
    compact = _compact(_pick(primary, "discrete"))
    assert compact["part_number"] == "DISC-B" and compact["loss_total_W_at_tj"] == pytest.approx(8.2)
    assert compact["rth_junction_to_case_K_per_W"] == pytest.approx(0.5)
    assert _bridge_block(s, "tertiary") == {}


def test_extension_schema_lists_every_task_block():
    schema = json.loads((Path(__file__).parents[1] / "src/aipe_workflows/schemas/dab-extension.schema.json").read_text(encoding="utf-8"))
    for key in ("analytic_sps", "magnetics_design", "semiconductor_screening", "control_baseline", "thermal_design", "fem_transformer_window",
                "fem_heatsink", "cad_transformer", "cad_heatsink"):
        assert key in schema["properties"], key


def test_kicad_report_summaries_and_clean_rule():
    erc = summarise_erc({"kicad_version": "10.0.6", "sheets": [{"violations": [{"severity": "warning", "type": "lib_symbol_mismatch"}]}, {"violations": []}]})
    assert erc == {"sheets": 2, "errors": 0, "warnings": 1, "excluded": 0, "total": 1, "types": {"lib_symbol_mismatch": 1}, "kicad_version": "10.0.6"}
    drc = summarise_drc({"violations": [{"severity": "error", "type": "clearance"}], "unconnected_items": [{"severity": "error", "type": "unconnected_items"}] * 3,
                         "schematic_parity": []})
    assert drc["violations"]["errors"] == 1 and drc["unconnected_items"]["total"] == 3 and drc["schematic_parity"]["total"] == 0
    assert not board_is_clean(erc, drc)
    clean_drc = summarise_drc({"violations": [{"severity": "warning", "type": "silk_overlap"}], "unconnected_items": [], "schematic_parity": []})
    assert board_is_clean(erc, clean_drc)
