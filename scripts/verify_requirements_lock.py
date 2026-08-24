"""Verifica a integridade e o formato do lock Python usado no build Windows."""
from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "requirements.lock"
HASH_FILE = ROOT / "requirements.lock.sha256"


def main() -> None:
    expected_hash, _, expected_name = HASH_FILE.read_text(encoding="utf-8").strip().partition("  ")
    if expected_name != LOCK_FILE.name or len(expected_hash) != 64:
        raise SystemExit("requirements.lock.sha256 tem formato invalido.")

    actual_hash = hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit("requirements.lock nao corresponde ao SHA-256 versionado.")

    package_lines = [
        line for line in LOCK_FILE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    if not package_lines or any("==" not in line for line in package_lines):
        raise SystemExit("requirements.lock precisa conter somente dependencias fixadas com ==.")

    print(f"Lock valido: {len(package_lines)} dependencias fixadas ({actual_hash[:12]}...).")


if __name__ == "__main__":
    main()
