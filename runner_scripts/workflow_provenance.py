import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_COMPONENTS = {
    "conan-package/workflow": ".github/workflows/conan-package.yml",
    "conan-recipe-version/workflow": ".github/workflows/conan-recipe-version.yml",
    "conan-recipe-version/setup-action": ".github/actions/setup-build-environment/action.yml",
    "conan-recipe-version/setup-helper-checkout": "Cura-workflows",
    "conan-recipe-export-specific/workflow": ".github/workflows/conan-recipe-export.yml",
    "conan-recipe-export-specific/setup-action": ".github/actions/setup-build-environment/action.yml",
    "conan-recipe-export-specific/setup-helper-checkout": "Cura-workflows",
    "conan-recipe-export-specific/upload-action": ".github/actions/upload-conan-package/action.yml",
    "conan-recipe-export-latest/workflow": ".github/workflows/conan-recipe-export.yml",
    "conan-recipe-export-latest/setup-action": ".github/actions/setup-build-environment/action.yml",
    "conan-recipe-export-latest/setup-helper-checkout": "Cura-workflows",
    "conan-recipe-export-latest/upload-action": ".github/actions/upload-conan-package/action.yml",
    "make-runners-list/workflow": ".github/workflows/make-runners-list.yml",
    "make-runners-list/script-checkout": "runner_scripts/make_runners_list.py",
    "conan-package-create/setup-action": ".github/actions/setup-build-environment/action.yml",
    "conan-package-create/setup-helper-checkout": "Cura-workflows",
}
REQUIRED_INSTANCES = set(REQUIRED_COMPONENTS)
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
CALLER_PATHS = {
    ".github/workflows/conan-package.yml",
    ".github/workflows/windows-arm.yml",
}


def _require_sha(value: str, name: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be an exact 40-hex SHA")
    return value.lower()


def verify_workflow_invocation(
    workflow_ref: str,
    workflow_sha: str,
    requested_ref: str,
    component_path: str,
    repository: str = "Ultimaker/Cura-workflows",
) -> None:
    requested = _require_sha(requested_ref, "requested ref")
    resolved = _require_sha(workflow_sha, "workflow SHA")
    if resolved != requested:
        raise ValueError("executed workflow SHA does not match requested ref")
    expected = f"{repository}/{component_path}@{requested_ref}".lower()
    if workflow_ref.lower() != expected:
        raise ValueError(f"executed workflow ref mismatch: {workflow_ref}")


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _require_line(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
        raise ValueError(f"validation caller does not pin {description}")


def validate_callers(repository: Path, validation_sha: str, workflow_sha: str) -> dict:
    validation = _require_sha(validation_sha, "validation SHA")
    workflow = _require_sha(workflow_sha, "workflow SHA")
    repository = repository.resolve()
    head = _require_sha(_git(repository, "rev-parse", "HEAD"), "checked-out source SHA")
    if head != validation:
        raise ValueError("checked-out source SHA does not match validation SHA")
    parents = _git(repository, "rev-list", "--parents", "-n", "1", validation_sha).split()
    if len(parents) != 2:
        raise ValueError("validation commit must have exactly one parent")
    implementation = _require_sha(parents[1], "implementation SHA")
    changed = {
        line.replace("\\", "/")
        for line in _git(repository, "diff", "--name-only", implementation, validation).splitlines()
        if line
    }
    if changed != CALLER_PATHS:
        raise ValueError("C..V must change exactly the two approved caller workflows")

    package = (repository / ".github" / "workflows" / "conan-package.yml").read_text(
        encoding="utf-8"
    )
    installer = (repository / ".github" / "workflows" / "windows-arm.yml").read_text(
        encoding="utf-8"
    )
    escaped = re.escape(workflow_sha)
    _require_line(
        package,
        rf"uses:\s*ultimaker/cura-workflows/\.github/workflows/conan-package\.yml@{escaped}\s*$",
        "the package workflow target to W",
    )
    _require_line(package, rf"cura_workflows_ref:\s*{escaped}\s*$", "package W input")
    for name, value in (
        ("allow_non_default_branch_package_create", "true"),
        ("platform_windows_arm64", "true"),
        ("platform_linux", "false"),
        ("platform_windows", "false"),
        ("platform_mac", "false"),
        ("platform_wasm", "false"),
    ):
        _require_line(package, rf"{name}:\s*{value}\s*$", f"package {name}={value}")

    _require_line(
        installer,
        rf"uses:\s*ultimaker/cura-workflows/\.github/workflows/cura-installer-windows-arm\.yml@{escaped}\s*$",
        "the installer workflow target to W",
    )
    _require_line(installer, rf"cura_workflows_ref:\s*{escaped}\s*$", "installer W input")
    for name in ("cura_conan_version", "package_workflow_run_id", "package_workflow_run_attempt"):
        _require_line(installer, rf"{name}:\s*\S+", f"installer {name} input")

    return {
        "schema_version": 1,
        "C": implementation,
        "V": validation,
        "W": workflow,
    }


def _validate_source_chain(chain: object) -> dict:
    if not isinstance(chain, dict) or chain.get("schema_version") != 1:
        raise ValueError("invalid source chain")
    for name in ("C", "V", "W"):
        _require_sha(chain.get(name, ""), name)
    return chain


def create_package_chain(
    source_chain: Path,
    package_reference: str,
    run_id: str,
    run_attempt: str,
    output: Path,
) -> None:
    chain = _validate_source_chain(json.loads(source_chain.read_text(encoding="utf-8")))
    if not package_reference or any(character.isspace() for character in package_reference):
        raise ValueError("package reference must be non-empty and contain no whitespace")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise ValueError("package run identity must be numeric")
    chain.update(
        {
            "package_reference": package_reference,
            "package_workflow_run_id": run_id,
            "package_workflow_run_attempt": run_attempt,
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(chain, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def validate_package_chain(
    chain_path: Path,
    source_chain_path: Path,
    package_reference: str,
    run_id: str,
    run_attempt: str,
    summary: Path | None = None,
) -> dict:
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    source = _validate_source_chain(json.loads(source_chain_path.read_text(encoding="utf-8")))
    expected = {
        **source,
        "package_reference": package_reference,
        "package_workflow_run_id": run_id,
        "package_workflow_run_attempt": run_attempt,
    }
    if chain != expected:
        raise ValueError("package chain does not match the installer C/V/W and package inputs")
    if summary:
        with summary.open("a", encoding="utf-8") as stream:
            stream.write(
                f"C={chain['C']}\nV={chain['V']}\nW={chain['W']}\n"
                f"package_reference={chain['package_reference']}\n"
                f"package_workflow_run={run_id}/{run_attempt}\n"
            )
    return chain


def create(output: Path, requested_ref: str, rows: list[str]) -> None:
    records = []
    for row in rows:
        fields = row.split("|")
        if len(fields) != 3 or not all(fields):
            raise ValueError(f"invalid provenance row: {row}")
        instance, component_path, resolved_sha = fields
        records.append(
            {
                "instance": instance,
                "component_path": component_path,
                "requested_ref": requested_ref,
                "resolved_sha": resolved_sha,
                "status": "PASS",
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def validate(directory: Path, requested_ref: str, summary: Path | None = None) -> list[dict]:
    records = []
    for path in sorted(directory.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise ValueError(f"{path} is not a provenance row list")
        records.extend(value)

    instances: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("provenance row must be an object")
        instance = record.get("instance")
        if not isinstance(instance, str) or not instance:
            raise ValueError("provenance row has no instance")
        if record.get("status") != "PASS":
            raise ValueError(f"non-PASS provenance instance: {instance}")
        if record.get("requested_ref") != requested_ref:
            raise ValueError(f"requested ref mismatch: {instance}")
        if record.get("component_path") != REQUIRED_COMPONENTS.get(instance):
            raise ValueError(f"component path mismatch: {instance}")
        resolved = record.get("resolved_sha")
        if not isinstance(resolved, str) or not SHA_PATTERN.fullmatch(resolved):
            raise ValueError(f"invalid resolved SHA: {instance}")
        if SHA_PATTERN.fullmatch(requested_ref) and resolved.lower() != requested_ref.lower():
            raise ValueError(f"resolved SHA mismatch: {instance}")
        if instance in instances:
            if instances[instance] != record:
                raise ValueError(f"conflicting duplicate provenance instance: {instance}")
            continue
        instances[instance] = record

    missing = REQUIRED_INSTANCES - instances.keys()
    unexpected = instances.keys() - REQUIRED_INSTANCES
    if missing:
        raise ValueError(f"missing provenance instances: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"unexpected provenance instances: {', '.join(sorted(unexpected))}")

    ordered = [instances[name] for name in sorted(instances)]
    if summary:
        with summary.open("a", encoding="utf-8") as stream:
            stream.write("| instance | component_path | requested_ref | resolved_sha | status |\n")
            stream.write("|---|---|---|---|---|\n")
            for record in ordered:
                stream.write(
                    "| {instance} | {component_path} | {requested_ref} | "
                    "{resolved_sha} | {status} |\n".format(**record)
                )
    return ordered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create or validate package provenance rows.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--output", required=True, type=Path)
    create_parser.add_argument("--requested-ref", required=True)
    create_parser.add_argument("--row", action="append", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--directory", required=True, type=Path)
    validate_parser.add_argument("--requested-ref", required=True)
    validate_parser.add_argument("--summary", type=Path)
    invocation_parser = subparsers.add_parser("verify-invocation")
    invocation_parser.add_argument("--workflow-ref", required=True)
    invocation_parser.add_argument("--workflow-sha", required=True)
    invocation_parser.add_argument("--requested-ref", required=True)
    invocation_parser.add_argument("--component-path", required=True)
    invocation_parser.add_argument("--repository", default="Ultimaker/Cura-workflows")
    callers_parser = subparsers.add_parser("validate-callers")
    callers_parser.add_argument("--repository", required=True, type=Path)
    callers_parser.add_argument("--validation-sha", required=True)
    callers_parser.add_argument("--workflow-sha", required=True)
    callers_parser.add_argument("--output", required=True, type=Path)
    create_chain_parser = subparsers.add_parser("create-package-chain")
    create_chain_parser.add_argument("--source-chain", required=True, type=Path)
    create_chain_parser.add_argument("--package-reference", required=True)
    create_chain_parser.add_argument("--run-id", required=True)
    create_chain_parser.add_argument("--run-attempt", required=True)
    create_chain_parser.add_argument("--output", required=True, type=Path)
    validate_chain_parser = subparsers.add_parser("validate-package-chain")
    validate_chain_parser.add_argument("--chain", required=True, type=Path)
    validate_chain_parser.add_argument("--source-chain", required=True, type=Path)
    validate_chain_parser.add_argument("--package-reference", required=True)
    validate_chain_parser.add_argument("--run-id", required=True)
    validate_chain_parser.add_argument("--run-attempt", required=True)
    validate_chain_parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create(args.output, args.requested_ref, args.row)
        elif args.command == "validate":
            validate(args.directory, args.requested_ref, args.summary)
        elif args.command == "verify-invocation":
            verify_workflow_invocation(
                args.workflow_ref,
                args.workflow_sha,
                args.requested_ref,
                args.component_path,
                args.repository,
            )
        elif args.command == "validate-callers":
            chain = validate_callers(args.repository, args.validation_sha, args.workflow_sha)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(chain, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        elif args.command == "create-package-chain":
            create_package_chain(
                args.source_chain,
                args.package_reference,
                args.run_id,
                args.run_attempt,
                args.output,
            )
        else:
            validate_package_chain(
                args.chain,
                args.source_chain,
                args.package_reference,
                args.run_id,
                args.run_attempt,
                args.summary,
            )
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
