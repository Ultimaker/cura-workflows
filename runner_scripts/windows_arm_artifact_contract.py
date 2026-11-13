import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
REQUIRED_METADATA = (
    "architecture",
    "expected_machine",
    "installer_filename",
    "cura_version_full",
    "cura_app_name",
    "cura_conan_reference",
    "caller_repository",
    "caller_sha",
    "cura_source_sha",
    "cura_implementation_sha",
    "cura_workflows_ref",
    "cura_workflows_sha",
    "workflow_ref",
    "run_id",
    "run_attempt",
    "runner.os",
    "runner.arch",
    "PROCESSOR_ARCHITECTURE",
    "python.executable",
    "python.base_prefix",
    "python.version",
    "python.machine",
    "python3_dll.source_path",
    "python3_dll.size",
    "python3_dll.sha256",
    "python3_dll.machine",
    "vs.installation_path",
    "vs.redist_version",
    "vs.crt_directory",
)


class ContractError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def safe_relative_path(value: str) -> str:
    if not isinstance(value, str):
        raise ContractError("path must be a string")
    normalized = value.replace("\\", "/")
    raw_parts = normalized.split("/")
    path = PurePosixPath(normalized)
    if (
        path.is_absolute()
        or re.match(r"^[A-Za-z]:", normalized)
        or not path.parts
        or any(part in ("", ".", "..") for part in raw_parts)
    ):
        raise ContractError(f"unsafe path: {value}")
    return path.as_posix()


def metadata_value(metadata: dict, dotted_name: str):
    if dotted_name in metadata:
        return metadata[dotted_name]
    value = metadata
    for part in dotted_name.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ContractError(f"missing required metadata: {dotted_name}")
        value = value[part]
    return value


def validate_metadata(metadata: object) -> dict:
    if not isinstance(metadata, dict):
        raise ContractError("metadata must be an object")
    for name in REQUIRED_METADATA:
        value = metadata_value(metadata, name)
        if value is None or value == "":
            raise ContractError(f"empty required metadata: {name}")
    if str(metadata_value(metadata, "architecture")).upper() != "ARM64":
        raise ContractError("metadata architecture must be ARM64")
    if str(metadata_value(metadata, "expected_machine")).upper() != "0XAA64":
        raise ContractError("metadata expected_machine must be 0xAA64")
    crt = metadata.get("crt")
    required_crt = {
        "concrt140.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    }
    if not isinstance(crt, list) or len(crt) != len(required_crt):
        raise ContractError("metadata crt must contain the six required runtime files")
    crt_names = set()
    for index, record in enumerate(crt):
        if not isinstance(record, dict):
            raise ContractError(f"metadata crt[{index}] must be an object")
        for field in ("name", "source_path", "size", "sha256", "machine"):
            if record.get(field) in (None, ""):
                raise ContractError(f"metadata crt[{index}].{field} is required")
        crt_names.add(record["name"].lower())
        if str(record["machine"]).upper() != "0XAA64":
            raise ContractError(f"metadata crt[{index}] is not Arm64")
    if crt_names != required_crt:
        raise ContractError("metadata crt names do not match the required runtime files")
    return metadata


def enumerate_includes(root: Path, includes: list[str]) -> list[tuple[str, Path]]:
    seen: set[str] = set()
    files: list[tuple[str, Path]] = []
    for include in includes:
        normalized = safe_relative_path(include)
        target = root.joinpath(*PurePosixPath(normalized).parts)
        if not target.exists():
            raise ContractError(f"included path is missing: {normalized}")
        if target.is_symlink():
            raise ContractError(f"included path is a symlink: {normalized}")
        if target.is_file():
            candidates = [target]
        else:
            candidates = []
            for path in target.rglob("*"):
                relative = safe_relative_path(path.relative_to(root).as_posix())
                if path.is_symlink():
                    raise ContractError(f"included path is a symlink: {relative}")
                if path.is_file():
                    candidates.append(path)
        for candidate in candidates:
            relative = safe_relative_path(candidate.relative_to(root).as_posix())
            folded = relative.casefold()
            if folded in seen:
                raise ContractError(f"duplicate included path: {relative}")
            seen.add(folded)
            files.append((relative, candidate))
    return sorted(files, key=lambda item: (item[0].casefold(), item[0]))


def create_contract(root: Path, metadata_path: Path, output: Path, includes: list[str]) -> None:
    root = root.resolve()
    metadata = validate_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))
    normalized_includes = [safe_relative_path(value) for value in includes]
    if len({value.casefold() for value in normalized_includes}) != len(normalized_includes):
        raise ContractError("duplicate include roots")
    records = []
    for relative, path in enumerate_includes(root, normalized_includes):
        data = path.read_bytes()
        records.append(
            {"path": relative, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    contract = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "includes": normalized_includes,
        "files": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(contract), encoding="utf-8")


def verify_contract(root: Path, contract_path: Path) -> None:
    root = root.resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or contract.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("unsupported contract schema")
    validate_metadata(contract.get("metadata"))
    includes = contract.get("includes")
    records = contract.get("files")
    if not isinstance(includes, list) or not includes or not all(isinstance(v, str) for v in includes):
        raise ContractError("contract includes must be a non-empty string list")
    if not isinstance(records, list):
        raise ContractError("contract files must be a list")

    expected: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ContractError("contract file record must be an object")
        relative = safe_relative_path(record.get("path", ""))
        folded = relative.casefold()
        if folded in expected:
            raise ContractError(f"duplicate contract path: {relative}")
        if not isinstance(record.get("size"), int) or record["size"] < 0:
            raise ContractError(f"invalid size for {relative}")
        digest = record.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ContractError(f"invalid SHA-256 for {relative}")
        expected[folded] = {**record, "path": relative}

    actual = enumerate_includes(root, includes)
    actual_paths = {relative.casefold() for relative, _ in actual}
    expected_paths = set(expected)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    if missing:
        raise ContractError(f"missing included files: {', '.join(missing)}")
    if extra:
        raise ContractError(f"extra included files: {', '.join(extra)}")
    for relative, path in actual:
        record = expected[relative.casefold()]
        data = path.read_bytes()
        if len(data) != record["size"]:
            raise ContractError(f"size mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != record["sha256"].lower():
            raise ContractError(f"SHA-256 mismatch: {relative}")


def verify_release_evidence(root: Path, evidence_path: Path) -> None:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    records = evidence.get("files") if isinstance(evidence, dict) else None
    if not isinstance(records, list) or len(records) != 2:
        raise ContractError("release evidence must identify exactly two installers")
    expected: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ContractError("release evidence file record must be an object")
        relative = safe_relative_path(record.get("path", ""))
        path = PurePosixPath(relative)
        if len(path.parts) != 2 or path.parts[0].casefold() != "installers":
            raise ContractError(f"release evidence path is not an installer: {relative}")
        filename = path.name
        if Path(filename).suffix.casefold() not in (".exe", ".msi"):
            raise ContractError(f"unexpected installer extension: {filename}")
        if filename.casefold() in expected:
            raise ContractError(f"duplicate release installer: {filename}")
        size = record.get("size")
        digest = record.get("sha256")
        if not isinstance(size, int) or size <= 0:
            raise ContractError(f"invalid release size: {filename}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ContractError(f"invalid release SHA-256: {filename}")
        expected[filename.casefold()] = record
    if {Path(record["path"]).suffix.casefold() for record in records} != {".exe", ".msi"}:
        raise ContractError("release evidence must contain one EXE and one MSI")

    actual = {path.name.casefold(): path for path in root.iterdir() if path.is_file()}
    if set(actual) != set(expected):
        raise ContractError("downloaded installer filenames do not match release evidence")
    for folded, path in actual.items():
        record = expected[folded]
        data = path.read_bytes()
        if len(data) != record["size"]:
            raise ContractError(f"release size mismatch: {path.name}")
        if hashlib.sha256(data).hexdigest() != record["sha256"].lower():
            raise ContractError(f"release SHA-256 mismatch: {path.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or verify a Windows Arm artifact contract.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--root", required=True, type=Path)
    create.add_argument("--metadata", required=True, type=Path)
    create.add_argument("--output", required=True, type=Path)
    create.add_argument("--include", required=True, action="append")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", required=True, type=Path)
    verify.add_argument("--contract", required=True, type=Path)
    verify_release = subparsers.add_parser("verify-release")
    verify_release.add_argument("--root", required=True, type=Path)
    verify_release.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_contract(args.root, args.metadata, args.output, args.include)
        elif args.command == "verify":
            verify_contract(args.root, args.contract)
        else:
            verify_release_evidence(args.root, args.evidence)
    except (ContractError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
