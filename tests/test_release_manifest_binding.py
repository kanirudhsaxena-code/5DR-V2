import json
from pathlib import Path

from src.engine_contract import MODEL_VERSION, OUTPUT_CONTRACT_VERSION

MANIFEST = Path("governance/production_release_manifest.json")

def test_release_manifest_binds_canonical_5dr_spec_to_runtime_contract():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "1.0"
    assert data["consumer"] == "5DR"
    assert data["binding_status"] == "BOUND"
    spec = data["master_spec"]
    binding = data["production_binding"]
    assert spec["canonical_spec_version"] == "5DR V2.2.3"
    assert len(spec["content_sha256_lf"]) == 64
    int(spec["content_sha256_lf"], 16)
    assert binding["model_version"] == MODEL_VERSION
    assert binding["output_contract_version"] == OUTPUT_CONTRACT_VERSION
    assert binding["methodology_status"] == "FROZEN_UNCHANGED"
    assert binding["screenshot_policy"] == "FALLBACK_ONLY"
