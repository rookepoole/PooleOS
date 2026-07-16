"""Owner-controlled ADR ratification artifacts and verification for PooleOS."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_RELATIVE = "specs/adr-ratification-policy.json"
POLICY_SCHEMA_RELATIVE = "specs/adr-ratification-policy.schema.json"
MANIFEST_SCHEMA_RELATIVE = "specs/adr-ratification-manifest.schema.json"
READINESS_SCHEMA_RELATIVE = "specs/adr-ratification-readiness.schema.json"
RECEIPT_SCHEMA_RELATIVE = "specs/adr-ratification-receipt.schema.json"
READINESS_RELATIVE = "runs/adr_ratification_readiness.json"
MANIFEST_RELATIVE = "runs/adr_ratification_manifest.json"
SIGNATURE_RELATIVE = "runs/adr_ratification_manifest.json.sig"
RECEIPT_RELATIVE = "runs/adr_ratification_receipt.json"

ADR_NAMES = (
    "0001-native-pooleos-constitution.md",
    "0002-reuse-clean-room-and-publication-boundary.md",
    "0003-language-and-toolchain-split.md",
    "0004-product-names-and-version-namespaces.md",
    "0005-v1-scope-mission-threats-and-non-goals.md",
    "0006-tcb-and-component-placement.md",
    "0007-repository-governance-and-source-tree.md",
)
ADR_IDS = tuple(f"ADR-{index:04d}" for index in range(1, 8))
ADR_HEADER_PATTERN = re.compile(r"^# ADR-(\d{4}): (.+)$")
FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z ]+):\s*(.*?)\s*$")


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def _safe_relative(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError(f"repository path must be relative: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"repository path escapes root: {relative!r}") from error
    return candidate


def bind_file(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_relative(root, relative)
    data = path.read_bytes()
    return {
        "path": relative.replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
    }


def load_policy(root: Path = ROOT) -> dict[str, Any]:
    return _read_json(root / POLICY_RELATIVE)


def parse_adr(root: Path, name: str) -> dict[str, Any]:
    relative = f"docs/adr/{name}"
    path = _safe_relative(root, relative)
    data = path.read_bytes()
    lines = data.decode("utf-8-sig").splitlines()
    heading = ADR_HEADER_PATTERN.fullmatch(lines[0]) if lines else None
    if heading is None:
        raise ValueError(f"invalid ADR heading: {relative}")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.startswith("## "):
            break
        match = FIELD_PATTERN.fullmatch(line.rstrip())
        if match:
            fields[match.group(1).casefold().replace(" ", "_")] = match.group(2).strip()
    for required in ("status", "date", "decision_owner", "ratification"):
        if required not in fields:
            raise ValueError(f"missing {required} in {relative}")

    return {
        "id": f"ADR-{heading.group(1)}",
        "title": heading.group(2),
        "path": relative,
        "source_status": fields["status"],
        "source_ratification": fields["ratification"],
        "decision_owner": fields["decision_owner"],
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
    }


def parse_adr_set(root: Path = ROOT) -> list[dict[str, Any]]:
    adrs = [parse_adr(root, name) for name in ADR_NAMES]
    if tuple(item["id"] for item in adrs) != ADR_IDS:
        raise ValueError("ADR set is not exactly ADR-0001 through ADR-0007")
    return adrs


def _public_key_fingerprint(key_blob_base64: str) -> str:
    try:
        blob = base64.b64decode(key_blob_base64.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as error:
        raise ValueError("allowed signer contains invalid public-key base64") from error
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def parse_allowed_signers(root: Path = ROOT, policy: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    policy = policy or load_policy(root)
    signature = policy["signature"]
    path = _safe_relative(root, signature["allowed_signers_path"])
    key_profiles = {item["key_type"]: item for item in signature["key_profiles"]}
    required_principal = signature["signer_principal"]
    required_namespaces = set(signature["required_allowed_namespaces"])
    signers: list[dict[str, Any]] = []
    errors: list[str] = []

    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = shlex.split(line, comments=False, posix=True)
        except ValueError:
            errors.append(f"allowed signer line {line_number} has invalid quoting")
            continue
        key_index = next((index for index, token in enumerate(tokens) if token in key_profiles), -1)
        if key_index < 1 or key_index + 1 >= len(tokens):
            errors.append(f"allowed signer line {line_number} has no supported public key")
            continue
        principals = set(tokens[0].split(","))
        if required_principal not in principals:
            errors.append(f"allowed signer line {line_number} omits principal {required_principal}")
            continue
        options = tokens[1:key_index]
        namespace_token = next((token for token in options if token.startswith("namespaces=")), "")
        namespaces = set(namespace_token.removeprefix("namespaces=").split(",")) if namespace_token else set()
        if not required_namespaces.issubset(namespaces):
            errors.append(f"allowed signer line {line_number} omits required signature namespaces")
            continue
        key_type = tokens[key_index]
        key_blob = tokens[key_index + 1]
        try:
            fingerprint = _public_key_fingerprint(key_blob)
        except ValueError as error:
            errors.append(f"allowed signer line {line_number}: {error}")
            continue
        signers.append(
            {
                "principal": required_principal,
                "key_type": key_type,
                "key_profile": key_profiles[key_type]["id"],
                "fingerprint": fingerprint,
                "namespaces": sorted(namespaces),
                "public_key": f"{key_type} {key_blob}",
            }
        )
    return signers, errors


def _schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    from runtime.schema_validation import validate_json

    schema = _read_json(root / schema_relative)
    return [f"{error.path}: {error.message}" for error in validate_json(value, schema)]


def build_readiness(root: Path = ROOT) -> dict[str, Any]:
    policy = load_policy(root)
    policy_errors = _schema_errors(policy, root, POLICY_SCHEMA_RELATIVE)
    adrs = parse_adr_set(root)
    status_counts = Counter(item["source_status"] for item in adrs)
    signers, signer_errors = parse_allowed_signers(root, policy)
    artifacts = {
        "manifest": {"path": MANIFEST_RELATIVE, "present": (root / MANIFEST_RELATIVE).is_file()},
        "signature": {"path": SIGNATURE_RELATIVE, "present": (root / SIGNATURE_RELATIVE).is_file()},
        "receipt": {"path": RECEIPT_RELATIVE, "present": (root / RECEIPT_RELATIVE).is_file()},
    }
    tooling_paths = (
        "runtime/adr_ratification.py",
        "tools/generate_adr_ratification_readiness.py",
        "tools/prepare_adr_ratification.py",
        "tools/verify_adr_ratification.py",
        "docs/adr-ratification-ceremony.md",
    )
    tooling_ready = all((root / path).is_file() for path in tooling_paths)
    pending_disposition = [item["id"] for item in adrs if item["source_status"] == "proposed"]
    ready_for_owner_action = not policy_errors and not signer_errors and tooling_ready and len(adrs) == 7
    ready_for_signature = (
        ready_for_owner_action
        and not pending_disposition
        and len(signers) == 1
        and artifacts["manifest"]["present"]
        and not artifacts["signature"]["present"]
    )

    owner_actions = [
        {
            "id": "OWNER-ADR-DISPOSITION-001",
            "status": "pending" if pending_disposition else "satisfied",
            "description": "Explicitly accept, amend, or reject ADR-0003 and ADR-0004; an amendment or rejection requires a revised or superseding ADR before signing.",
        },
        {
            "id": "OWNER-SIGNING-CUSTODY-001",
            "status": "pending" if not signers else "satisfied",
            "description": "Choose an allowed owner-controlled SSH governance-key profile and record its public key and fingerprint without publishing private material.",
        },
        {
            "id": "OWNER-DETACHED-SIGN-001",
            "status": "pending" if not artifacts["signature"]["present"] else "evidence_present_unverified",
            "description": "Sign the canonical manifest with the PooleOS ADR namespace and verify it against the public allowed-signers and revocation files.",
        },
        {
            "id": "OWNER-SIGNED-TAG-001",
            "status": "pending",
            "description": "Create the non-replaceable owner-signed annotated architecture baseline tag over the revision carrying the manifest and detached signature.",
        },
        {
            "id": "OWNER-PUBLISH-RECEIPT-001",
            "status": "pending" if not artifacts["receipt"]["present"] else "evidence_present_unverified",
            "description": "Publish the exact main revision and signed tag, verify remote object identities, and retain the machine receipt.",
        },
    ]

    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_adr_ratification_readiness",
        "status_date": policy["status_date"],
        "status": "pending_owner_action",
        "selected_move_id": "N0-RATIFY-001",
        "production_ready": False,
        "production_promotion_allowed": False,
        "policy": bind_file(root, POLICY_RELATIVE),
        "adr_set": {
            "required_count": 7,
            "present_count": len(adrs),
            "accepted_owner_directed_count": status_counts["accepted-owner-directed"],
            "proposed_count": status_counts["proposed"],
            "cryptographically_ratified_count": 0,
            "pending_owner_disposition": pending_disposition,
            "adrs": adrs,
        },
        "trust_bootstrap": {
            "backend": policy["signature"]["backend"],
            "format": policy["signature"]["format"],
            "namespace": policy["signature"]["namespace"],
            "signer_principal": policy["signature"]["signer_principal"],
            "allowed_signers_path": policy["signature"]["allowed_signers_path"],
            "revocation_path": policy["signature"]["revocation_path"],
            "trusted_signer_count": len(signers),
            "signer_file_errors": signer_errors,
        },
        "artifacts": artifacts,
        "summary": {
            "policy_schema_valid": not policy_errors,
            "required_adr_set_complete": len(adrs) == 7,
            "ratification_tooling_present": tooling_ready,
            "ready_for_owner_action": ready_for_owner_action,
            "ready_for_signature": ready_for_signature,
            "blocking_owner_action_count": sum(item["status"] == "pending" for item in owner_actions),
            "defined_negative_control_count": len(policy["negative_controls"]),
        },
        "owner_actions": owner_actions,
        "claim_boundary": [
            "This readiness ledger is unsigned preparation evidence and is not owner acceptance.",
            "No private key, credential, recovery secret, or hardware-backed key handle is recorded.",
            "A detached signature alone does not satisfy the signed-tag and remote-publication gates.",
            "Architecture ratification does not prove a bootloader, kernel, driver, desktop, or production ISO.",
        ],
    }


def build_manifest(
    root: Path = ROOT,
    *,
    owner_accept_all_exact: bool,
    accept_software_key_risk: bool = False,
) -> dict[str, Any]:
    if not owner_accept_all_exact:
        raise ValueError("owner_accept_all_exact is required; no ADR disposition is inferred")
    policy = load_policy(root)
    if _schema_errors(policy, root, POLICY_SCHEMA_RELATIVE):
        raise ValueError("ratification policy does not satisfy its schema")
    signers, signer_errors = parse_allowed_signers(root, policy)
    if signer_errors:
        raise ValueError("allowed-signers file is invalid: " + "; ".join(signer_errors))
    if len(signers) != 1:
        raise ValueError("exactly one owner bootstrap signer is required to prepare the first manifest")
    signer = signers[0]
    profiles = {item["id"]: item for item in policy["signature"]["key_profiles"]}
    profile = profiles[signer["key_profile"]]
    if profile["owner_risk_acceptance_required"] and not accept_software_key_risk:
        raise ValueError("the provisional software key profile requires explicit owner risk acceptance")

    adrs = parse_adr_set(root)
    decisions = [
        {
            **adr,
            "disposition": "accept_exact_bytes",
            "effective_status_after_valid_signature": "accepted-signed",
        }
        for adr in adrs
    ]
    signature = policy["signature"]
    manifest = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_adr_ratification_manifest",
        "canonicalization": policy["canonical_manifest"],
        "repository": policy["repository"],
        "decision_owner": policy["decision_owner"],
        "owner_acceptance": {
            "action": "accept_exact_bytes",
            "statement": "By signing these canonical bytes, Rooke Poole accepts every listed ADR and bound source exactly as identified.",
            "required_adr_count": 7,
            "accepted_exact_count": 7,
            "decisions": decisions,
        },
        "bound_sources": [bind_file(root, path) for path in policy["required_bound_sources"]],
        "policy_binding": bind_file(root, POLICY_RELATIVE),
        "signer": {
            "principal": signer["principal"],
            "key_type": signer["key_type"],
            "key_profile": signer["key_profile"],
            "public_key_fingerprint": signer["fingerprint"],
            "software_key_risk_explicitly_accepted": bool(profile["owner_risk_acceptance_required"]),
        },
        "signature_contract": {
            "backend": signature["backend"],
            "format": signature["format"],
            "namespace": signature["namespace"],
            "hash_algorithm": signature["hash_algorithm"],
            "allowed_signers_path": signature["allowed_signers_path"],
            "revocation_path": signature["revocation_path"],
        },
        "tag_contract": policy["tag"],
        "claim_boundary": [
            "This manifest has no authority until its exact canonical bytes carry a valid owner-controlled detached signature.",
            "The detached signature ratifies architecture decisions; it is not a PooleOS binary, Secure Boot, package, update, or release-media signature.",
            "Production promotion additionally requires the signed annotated tag and exact remote-publication receipt defined by this manifest.",
        ],
    }
    errors = _schema_errors(manifest, root, MANIFEST_SCHEMA_RELATIVE)
    if errors:
        raise ValueError("generated manifest is invalid: " + "; ".join(errors[:8]))
    return manifest


def validate_manifest(root: Path, manifest_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [f"manifest cannot be decoded: {type(error).__name__}"]
    if not isinstance(manifest, dict):
        return None, ["manifest root is not an object"]
    errors.extend(_schema_errors(manifest, root, MANIFEST_SCHEMA_RELATIVE))
    if raw != canonical_json_bytes(manifest):
        errors.append("manifest bytes are not canonical sorted UTF-8 JSON with LF and one trailing newline")
    try:
        expected = build_manifest(
            root,
            owner_accept_all_exact=True,
            accept_software_key_risk=bool(
                manifest.get("signer", {}).get("software_key_risk_explicitly_accepted", False)
            ),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"cannot reconstruct expected manifest: {error}")
    else:
        if manifest != expected:
            errors.append("manifest does not match the current exact ADR, source, policy, or signer bindings")
    return manifest, errors


def _has_noncomment_lines(path: Path) -> bool:
    if not path.is_file():
        return False
    return any(line.strip() and not line.lstrip().startswith("#") for line in path.read_text(encoding="utf-8-sig").splitlines())


def verify_detached_signature(
    root: Path,
    manifest_path: Path,
    signature_path: Path,
    policy: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    policy = policy or load_policy(root)
    executable = shutil.which(policy["signature"]["executable"])
    if executable is None:
        return False, "OpenSSH ssh-keygen is unavailable"
    signature = policy["signature"]
    command = [
        executable,
        "-Y",
        "verify",
        "-f",
        str(_safe_relative(root, signature["allowed_signers_path"])),
        "-I",
        signature["signer_principal"],
        "-n",
        signature["namespace"],
    ]
    revocation_path = _safe_relative(root, signature["revocation_path"])
    if _has_noncomment_lines(revocation_path):
        command.extend(["-r", str(revocation_path)])
    command.extend(["-s", str(signature_path)])
    completed = subprocess.run(
        command,
        input=manifest_path.read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode == 0, "valid owner principal and namespace" if completed.returncode == 0 else "signature verification failed"


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("git")
    if executable is None:
        return subprocess.CompletedProcess(args, 127, b"", b"git unavailable")
    return subprocess.run(
        [executable, *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def verify_signed_tag(
    root: Path,
    manifest_path: Path,
    signature_path: Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy(root)
    tag_name = policy["tag"]["name"]
    tag_ref = f"refs/tags/{tag_name}"
    tag_type = _git(root, ["cat-file", "-t", tag_ref])
    present = tag_type.returncode == 0 and tag_type.stdout.strip() == b"tag"
    result = {
        "name": tag_name,
        "present": present,
        "signature_verified": False,
        "target_commit": "",
        "contains_manifest": False,
        "contains_signature": False,
    }
    if not present:
        return result

    signature = policy["signature"]
    verify_args = [
        "-c",
        "gpg.format=ssh",
        "-c",
        f"gpg.ssh.allowedSignersFile={_safe_relative(root, signature['allowed_signers_path'])}",
        "-c",
        "gpg.minTrustLevel=fully",
    ]
    revocation_path = _safe_relative(root, signature["revocation_path"])
    if _has_noncomment_lines(revocation_path):
        verify_args.extend(["-c", f"gpg.ssh.revocationFile={revocation_path}"])
    verified = _git(root, [*verify_args, "verify-tag", tag_name])
    result["signature_verified"] = verified.returncode == 0

    target = _git(root, ["rev-parse", f"{tag_name}^{{commit}}"])
    if target.returncode != 0:
        return result
    target_commit = target.stdout.decode("ascii", errors="ignore").strip()
    result["target_commit"] = target_commit
    manifest_blob = _git(root, ["show", f"{target_commit}:{MANIFEST_RELATIVE}"])
    signature_blob = _git(root, ["show", f"{target_commit}:{SIGNATURE_RELATIVE}"])
    result["contains_manifest"] = manifest_blob.returncode == 0 and manifest_blob.stdout == manifest_path.read_bytes()
    result["contains_signature"] = signature_blob.returncode == 0 and signature_blob.stdout == signature_path.read_bytes()
    return result


def verify_remote_publication(root: Path, tag_info: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy(root)
    tag_name = policy["tag"]["name"]
    remote = policy["remote_publication"]["remote"]
    default_branch = policy["repository"]["default_branch"]
    result = {
        "required": True,
        "checked": True,
        "remote": remote,
        "expected_remote_url": policy["repository"]["remote_url"],
        "configured_remote_url": "",
        "remote_url_match": False,
        "default_branch": default_branch,
        "main_commit": "",
        "tag_object": "",
        "peeled_commit": "",
        "exact_main_tip_match": False,
        "published": False,
    }
    configured_remote = _git(root, ["remote", "get-url", remote])
    if configured_remote.returncode != 0:
        return result
    result["configured_remote_url"] = configured_remote.stdout.decode("utf-8", errors="ignore").strip()
    result["remote_url_match"] = result["configured_remote_url"] == result["expected_remote_url"]
    if not result["remote_url_match"]:
        return result
    local_tag = _git(root, ["rev-parse", f"refs/tags/{tag_name}"])
    if local_tag.returncode != 0:
        return result
    completed = _git(
        root,
        [
            "ls-remote",
            remote,
            f"refs/heads/{default_branch}",
            f"refs/tags/{tag_name}",
            f"refs/tags/{tag_name}^{{}}",
        ],
    )
    if completed.returncode != 0:
        return result
    refs: dict[str, str] = {}
    for raw_line in completed.stdout.decode("ascii", errors="ignore").splitlines():
        parts = raw_line.split("\t", 1)
        if len(parts) == 2:
            refs[parts[1]] = parts[0]
    result["main_commit"] = refs.get(f"refs/heads/{default_branch}", "")
    result["tag_object"] = refs.get(f"refs/tags/{tag_name}", "")
    result["peeled_commit"] = refs.get(f"refs/tags/{tag_name}^{{}}", "")
    local_tag_object = local_tag.stdout.decode("ascii", errors="ignore").strip()
    target = str(tag_info.get("target_commit", ""))
    result["exact_main_tip_match"] = bool(target and result["main_commit"] == target)
    result["published"] = bool(
        result["remote_url_match"]
        and result["exact_main_tip_match"]
        and result["tag_object"] == local_tag_object
        and result["peeled_commit"] == target
    )
    return result


def build_receipt(
    root: Path = ROOT,
    *,
    manifest_path: Path | None = None,
    signature_path: Path | None = None,
    verify_remote: bool = False,
    observed_at_utc: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(root)
    manifest_path = manifest_path or root / MANIFEST_RELATIVE
    signature_path = signature_path or root / SIGNATURE_RELATIVE
    observed_at_utc = observed_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    signers, signer_errors = parse_allowed_signers(root, policy)
    manifest_present = manifest_path.is_file()
    signature_present = signature_path.is_file()
    manifest: dict[str, Any] | None = None
    manifest_errors: list[str] = []
    canonical = False
    if manifest_present:
        manifest, manifest_errors = validate_manifest(root, manifest_path)
        canonical = bool(manifest is not None and manifest_path.read_bytes() == canonical_json_bytes(manifest))

    detached_verified = False
    detached_detail = "not attempted"
    partial_artifacts = manifest_present != signature_present
    if manifest_present and signature_present and not manifest_errors and not signer_errors and signers:
        detached_verified, detached_detail = verify_detached_signature(root, manifest_path, signature_path, policy)

    tag_info = {
        "name": policy["tag"]["name"],
        "present": False,
        "signature_verified": False,
        "target_commit": "",
        "contains_manifest": False,
        "contains_signature": False,
    }
    if detached_verified:
        tag_info = verify_signed_tag(root, manifest_path, signature_path, policy)
    tag_verified = bool(
        tag_info["present"]
        and tag_info["signature_verified"]
        and tag_info["contains_manifest"]
        and tag_info["contains_signature"]
    )
    remote_info = {
        "required": True,
        "checked": False,
        "remote": policy["remote_publication"]["remote"],
        "expected_remote_url": policy["repository"]["remote_url"],
        "configured_remote_url": "",
        "remote_url_match": False,
        "default_branch": policy["repository"]["default_branch"],
        "main_commit": "",
        "tag_object": "",
        "peeled_commit": "",
        "exact_main_tip_match": False,
        "published": False,
    }
    if tag_verified and verify_remote:
        remote_info = verify_remote_publication(root, tag_info, policy)

    invalid = bool(
        partial_artifacts
        or signer_errors
        or (manifest_present and not signers)
        or manifest_errors
        or (manifest_present and signature_present and not detached_verified)
        or (tag_info["present"] and not tag_verified)
        or (verify_remote and tag_verified and not remote_info["published"])
    )
    if invalid:
        status = "invalid"
    elif not detached_verified:
        status = "pending_owner_action"
    elif not tag_verified:
        status = "detached_signature_verified_tag_pending"
    elif not verify_remote or not remote_info["published"]:
        status = "local_tag_verified_publication_pending"
    else:
        status = "verified"
    promotion_allowed = status == "verified"

    manifest_data = manifest_path.read_bytes() if manifest_present else b""
    signature_data = signature_path.read_bytes() if signature_present else b""
    signer = signers[0] if len(signers) == 1 else None
    checks = [
        {"name": "policy_schema_valid", "ok": not _schema_errors(policy, root, POLICY_SCHEMA_RELATIVE), "detail": "frozen policy"},
        {"name": "single_trusted_owner_signer", "ok": len(signers) == 1 and not signer_errors, "detail": f"trusted_signers={len(signers)}"},
        {"name": "manifest_present", "ok": manifest_present, "detail": MANIFEST_RELATIVE},
        {"name": "manifest_canonical", "ok": canonical and not manifest_errors, "detail": "exact canonical bytes" if canonical else "pending or invalid"},
        {"name": "detached_signature_present", "ok": signature_present, "detail": SIGNATURE_RELATIVE},
        {"name": "detached_signature_verified", "ok": detached_verified, "detail": detached_detail},
        {"name": "signed_annotated_tag_verified", "ok": tag_verified, "detail": policy["tag"]["name"]},
        {"name": "exact_remote_publication_verified", "ok": remote_info["published"], "detail": "remote main and tag objects match" if remote_info["published"] else "pending"},
        {"name": "production_readiness_not_overclaimed", "ok": True, "detail": "production_ready=false"},
    ]
    receipt = {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_adr_ratification_receipt",
        "observed_at_utc": observed_at_utc,
        "status": status,
        "production_ready": False,
        "production_promotion_allowed": promotion_allowed,
        "manifest": {
            "path": MANIFEST_RELATIVE,
            "present": manifest_present,
            "canonical": canonical,
            "sha256": sha256_bytes(manifest_data) if manifest_data else "",
            "byte_count": len(manifest_data),
        },
        "detached_signature": {
            "path": SIGNATURE_RELATIVE,
            "present": signature_present,
            "verified": detached_verified,
            "sha256": sha256_bytes(signature_data) if signature_data else "",
            "byte_count": len(signature_data),
            "namespace": policy["signature"]["namespace"],
            "principal": policy["signature"]["signer_principal"],
        },
        "signer": {
            "allowed_signers_path": policy["signature"]["allowed_signers_path"],
            "trusted_signer_count": len(signers),
            "key_type": signer["key_type"] if signer else "",
            "key_profile": signer["key_profile"] if signer else "",
            "public_key_fingerprint": signer["fingerprint"] if signer else "",
        },
        "signed_tag": tag_info,
        "remote_publication": remote_info,
        "ratification": {
            "required_adr_count": 7,
            "accepted_exact_count": 7 if detached_verified else 0,
            "all_required_cryptographically_ratified": detached_verified,
            "full_n0_exit_evidence_present": promotion_allowed,
        },
        "checks": checks,
        "errors": [*signer_errors, *manifest_errors],
        "claim_boundary": [
            "production_ready remains false even when architecture ratification verifies.",
            "The receipt does not sign PooleBoot, PooleKernel, packages, updates, Secure Boot databases, or ISO media.",
            "Remote publication is accepted only when remote main, the annotated tag object, and its peeled commit match the locally verified ceremony objects.",
        ],
    }
    schema_errors = _schema_errors(receipt, root, RECEIPT_SCHEMA_RELATIVE)
    if schema_errors:
        raise ValueError("ratification receipt does not satisfy its schema: " + "; ".join(schema_errors[:8]))
    return receipt


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
