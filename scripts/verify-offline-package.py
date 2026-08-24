"""Validate an extracted offline package without contacting a package index."""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path


REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_dir", type=Path)
    args = parser.parse_args()
    root = args.package_dir.resolve()
    lock = root / "requirements-runtime.lock"
    wheels = root / "wheels"
    required_files = ["Setup-Offline.ps1", "Executar.ps1", "launch.ps1", "backend.py", "README-OFFLINE.md"]

    missing = [name for name in required_files if not (root / name).is_file()]
    if missing:
        raise SystemExit(f"Arquivos obrigatorios ausentes: {', '.join(missing)}")
    if not lock.is_file() or not wheels.is_dir():
        raise SystemExit("Lockfile ou diretorio wheels ausente.")

    required = []
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT.match(line)
        if match:
            required.append((normalized(match.group(1)), match.group(2)))

    available: set[tuple[str, str]] = set()
    for wheel in wheels.glob("*.whl"):
        with zipfile.ZipFile(wheel) as archive:
            metadata_name = next(
                (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")), None
            )
            if metadata_name is None:
                raise SystemExit(f"Wheel sem METADATA: {wheel.name}")
            metadata = archive.read(metadata_name).decode("utf-8")
        name = re.search(r"^Name: (.+)$", metadata, re.MULTILINE)
        version = re.search(r"^Version: (.+)$", metadata, re.MULTILINE)
        if name is None or version is None:
            raise SystemExit(f"METADATA invalido: {wheel.name}")
        available.add((normalized(name.group(1).strip()), version.group(1).strip()))

    absent = sorted(set(required) - available)
    if absent:
        formatted = ", ".join(f"{name}=={version}" for name, version in absent)
        raise SystemExit(f"Wheels ausentes para: {formatted}")
    print(f"Pacote offline valido: {len(required)} dependencias e {len(list(wheels.glob('*.whl')))} wheels.")


if __name__ == "__main__":
    main()
