from __future__ import annotations

from pathlib import Path

import app.services.changelog as changelog_module
from app.services.changelog import (
    latest_version,
    newer_entries,
    parse_changelog,
    version_gt,
    version_tuple,
)

SAMPLE = """# Changelog

## 0.2.0 - 2026-12-01
- Nueva función.
- Otra mejora.

## 0.1.1 - 2026-11-16
- Página de novedades.
- Correcciones.

## 0.1.0 - 2026-11-01
- Primera versión.
"""


def test_parse_changelog_orders_versions() -> None:
    entries = parse_changelog(SAMPLE)
    assert [entry.version for entry in entries] == ["0.2.0", "0.1.1", "0.1.0"]
    assert entries[0].date == "2026-12-01"
    assert entries[0].notes == ["Nueva función.", "Otra mejora."]


def test_newer_entries_filters_installed_versions() -> None:
    entries = parse_changelog(SAMPLE)
    newer = newer_entries(entries, "0.1.0")
    assert [entry.version for entry in newer] == ["0.2.0", "0.1.1"]
    assert newer_entries(entries, "0.2.0") == []


def test_version_comparison() -> None:
    assert version_tuple("1.2.3") == (1, 2, 3)
    assert version_gt("1.2.4", "1.2.3")
    assert not version_gt("1.2.3", "1.2.3")
    assert latest_version(parse_changelog(SAMPLE), "0.0.1") == "0.2.0"


def test_repository_changelog_contains_current_version() -> None:
    path = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    entries = parse_changelog(path.read_text(encoding="utf-8"))
    assert any(entry.version == "0.1.1" for entry in entries)
    assert any(entry.version == "0.1.0" for entry in entries)


async def test_supervisor_changelog_filters_installed_version(monkeypatch) -> None:
    monkeypatch.setattr(changelog_module, "SUPERVISOR_TOKEN", "test-token")

    async def fake_get(path: str):
        if path.endswith("/addons/self/info"):
            return {
                "version": "0.1.0",
                "version_latest": "0.2.0",
                "slug": "local_energyhub",
                "changelog": True,
            }
        return SAMPLE

    monkeypatch.setattr(changelog_module, "_supervisor_get", fake_get)
    result = await changelog_module._try_supervisor("0.1.0")
    assert result is not None
    assert result.source == "supervisor"
    assert result.checked is True
    assert result.update_available is True
    assert [entry.version for entry in result.entries] == ["0.2.0", "0.1.1"]
