import copy
import hashlib
import json
from pathlib import Path

import pytest

from runner_scripts import windows_arm_artifact_contract as contract


def metadata():
    value = {
        "architecture": "ARM64",
        "expected_machine": "0xAA64",
        "installer_filename": "Cura-win64-ARM64",
        "cura_version_full": "1.2.3",
        "cura_app_name": "Cura",
        "cura_conan_reference": "cura/1.2.3@u/c",
        "caller_repository": "Ultimaker/Cura",
        "caller_sha": "a" * 40,
        "cura_source_sha": "a" * 40,
        "cura_implementation_sha": "b" * 40,
        "cura_workflows_ref": "c" * 40,
        "cura_workflows_sha": "c" * 40,
        "workflow_ref": "Ultimaker/Cura/.github/workflows/windows-arm.yml@refs/heads/test",
        "run_id": "1",
        "run_attempt": "1",
        "runner": {"os": "Windows", "arch": "ARM64"},
        "PROCESSOR_ARCHITECTURE": "ARM64",
        "python": {
            "executable": "python.exe",
            "base_prefix": "C:\\Python",
            "version": "3.13.1",
            "machine": "ARM64",
        },
        "python3_dll": {
            "source_path": "C:\\Python\\python3.dll",
            "size": 123,
            "sha256": "d" * 64,
            "machine": "0xAA64",
        },
        "vs": {
            "installation_path": "C:\\VS",
            "redist_version": "14.40",
            "crt_directory": "C:\\VS\\CRT",
        },
        "crt": [
            {
                "name": name,
                "source_path": f"C:\\VS\\CRT\\{name}",
                "size": 123,
                "sha256": "e" * 64,
                "machine": "0xAA64",
            }
            for name in (
                "concrt140.dll",
                "msvcp140.dll",
                "msvcp140_1.dll",
                "msvcp140_2.dll",
                "vcruntime140.dll",
                "vcruntime140_1.dll",
            )
        ],
    }
    return value


def make_root(tmp_path):
    (tmp_path / "payload").mkdir()
    (tmp_path / "payload" / "app.exe").write_bytes(b"application")
    (tmp_path / "packaging").mkdir()
    (tmp_path / "packaging" / "recipe.txt").write_text("recipe", encoding="utf-8")
    (tmp_path / "metadata").mkdir()
    (tmp_path / "metadata" / "unsigned-pe.json").write_text("{}", encoding="utf-8")
    metadata_path = tmp_path / "metadata-source.json"
    metadata_path.write_text(json.dumps(metadata()), encoding="utf-8")
    output = tmp_path / "metadata" / "build-contract.json"
    return metadata_path, output


def create(tmp_path):
    metadata_path, output = make_root(tmp_path)
    contract.create_contract(
        tmp_path,
        metadata_path,
        output,
        ["payload", "packaging", "metadata/unsigned-pe.json"],
    )
    return output


def test_round_trip_and_canonical_output(tmp_path):
    output = create(tmp_path)
    contract.verify_contract(tmp_path, output)
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert output.read_text(encoding="utf-8") == contract.canonical_json(parsed)
    assert [record["path"] for record in parsed["files"]] == sorted(
        record["path"] for record in parsed["files"]
    )


@pytest.mark.parametrize("change", ["mutation", "deletion", "addition"])
def test_file_set_and_content_changes_fail(tmp_path, change):
    output = create(tmp_path)
    target = tmp_path / "payload" / "app.exe"
    if change == "mutation":
        target.write_bytes(b"changed")
    elif change == "deletion":
        target.unlink()
    else:
        (tmp_path / "payload" / "extra.dll").write_bytes(b"extra")
    with pytest.raises(contract.ContractError):
        contract.verify_contract(tmp_path, output)


def test_traversal_and_duplicate_contract_paths_fail(tmp_path):
    output = create(tmp_path)
    parsed = json.loads(output.read_text(encoding="utf-8"))
    traversed = copy.deepcopy(parsed)
    traversed["files"][0]["path"] = "../escape"
    output.write_text(json.dumps(traversed), encoding="utf-8")
    with pytest.raises(contract.ContractError, match="unsafe path"):
        contract.verify_contract(tmp_path, output)

    duplicated = copy.deepcopy(parsed)
    duplicated["files"].append(copy.deepcopy(duplicated["files"][0]))
    output.write_text(json.dumps(duplicated), encoding="utf-8")
    with pytest.raises(contract.ContractError, match="duplicate contract path"):
        contract.verify_contract(tmp_path, output)


def test_symlinked_include_is_rejected(tmp_path, monkeypatch):
    metadata_path, output = make_root(tmp_path)
    target = tmp_path / "payload" / "app.exe"
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == target or original_is_symlink(path),
    )
    with pytest.raises(contract.ContractError, match="included path is a symlink"):
        contract.create_contract(tmp_path, metadata_path, output, ["payload"])


def test_malformed_required_metadata_fails(tmp_path):
    metadata_path, output = make_root(tmp_path)
    broken = metadata()
    del broken["python"]["machine"]
    metadata_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(contract.ContractError, match="python.machine"):
        contract.create_contract(tmp_path, metadata_path, output, ["payload"])


def test_release_evidence_binds_downloaded_installer_hashes_and_sizes(tmp_path):
    installers = tmp_path / "installers"
    installers.mkdir()
    files = {
        "Cura-win64-ARM64.exe": b"signed exe",
        "Cura-win64-ARM64.msi": b"signed msi",
    }
    for name, data in files.items():
        (installers / name).write_bytes(data)
    evidence = tmp_path / "release-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": f"installers/{name}",
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                    for name, data in files.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    contract.verify_release_evidence(installers, evidence)

    (installers / "Cura-win64-ARM64.exe").write_bytes(b"substituted")
    with pytest.raises(contract.ContractError, match="release (size|SHA-256) mismatch"):
        contract.verify_release_evidence(installers, evidence)
