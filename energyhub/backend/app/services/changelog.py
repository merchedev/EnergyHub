from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..config import APP_VERSION, CHANGELOG_URL, FULL_CHANGELOG_URL, SUPERVISOR_TOKEN

SUPERVISOR_BASE = "http://supervisor"
ADDON_SLUG = os.getenv("ENERGYHUB_SLUG", "energyhub")
VERSION_RE = re.compile(
    r"^##\s+\[?v?(\d+\.\d+\.\d+)\]?(?:\s*[-–]\s*(\d{4}-\d{2}-\d{2}))?"
)


@dataclass
class ChangelogEntry:
    version: str
    date: str | None
    notes: list[str]

    def as_dict(self) -> dict:
        return {"version": self.version, "date": self.date, "notes": self.notes}


@dataclass
class ChangelogResult:
    installed_version: str
    latest_version: str
    entries: list[ChangelogEntry]
    update_available: bool
    source: str
    checked: bool
    full_changelog_url: str
    error: str | None = None
    fetched_at: str | None = None

    def as_dict(self) -> dict:
        return {
            "installed_version": self.installed_version,
            "latest_version": self.latest_version,
            "entries": [entry.as_dict() for entry in self.entries],
            "update_available": self.update_available,
            "source": self.source,
            "checked": self.checked,
            "full_changelog_url": self.full_changelog_url,
            "error": self.error,
            "fetched_at": self.fetched_at,
        }


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", value or "")
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def version_gt(left: str, right: str) -> bool:
    return version_tuple(left) > version_tuple(right)


def parse_changelog(text: str) -> list[ChangelogEntry]:
    entries: list[ChangelogEntry] = []
    current: ChangelogEntry | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = VERSION_RE.match(line)
        if match:
            if current is not None:
                entries.append(current)
            current = ChangelogEntry(version=match.group(1), date=match.group(2), notes=[])
            continue
        if current is None:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("- "):
            note = line[2:].strip()
        elif line.startswith("* "):
            note = line[2:].strip()
        else:
            note = line
        if note:
            current.notes.append(note)
    if current is not None:
        entries.append(current)
    entries.sort(key=lambda entry: version_tuple(entry.version), reverse=True)
    return entries


def newer_entries(entries: list[ChangelogEntry], installed_version: str) -> list[ChangelogEntry]:
    return [entry for entry in entries if version_gt(entry.version, installed_version)]


def latest_version(entries: list[ChangelogEntry], fallback: str) -> str:
    if not entries:
        return fallback
    return max((entry.version for entry in entries), key=version_tuple)


def _local_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[2] / "CHANGELOG.md",
        here.parents[3] / "CHANGELOG.md",
        Path.cwd() / "CHANGELOG.md",
        Path.cwd().parent / "CHANGELOG.md",
    ]


def _read_local() -> str | None:
    for path in _local_candidates():
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


async def _fetch_remote() -> str:
    headers = {"User-Agent": "EnergyHub/0.1 (Home Assistant energy estimator)"}
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        response = await client.get(CHANGELOG_URL, headers=headers)
        response.raise_for_status()
        return response.text


async def _supervisor_get(path: str) -> str | dict:
    if not SUPERVISOR_TOKEN:
        raise RuntimeError("SUPERVISOR_TOKEN no disponible")
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{SUPERVISOR_BASE}{path}", headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        return response.text


async def _try_supervisor(installed_version: str) -> ChangelogResult | None:
    if not SUPERVISOR_TOKEN:
        return None
    try:
        info = await _supervisor_get("/addons/self/info")
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    reported_installed = str(info.get("version") or installed_version)
    latest = str(info.get("version_latest") or reported_installed)
    slug = str(info.get("slug") or ADDON_SLUG)
    update_available = version_gt(latest, reported_installed)
    text: str | None = None
    error: str | None = None
    if update_available and bool(info.get("changelog")):
        try:
            raw = await _supervisor_get(f"/store/addons/{slug}/changelog")
            if isinstance(raw, str):
                text = raw
        except Exception:
            error = "No se ha podido leer el changelog de la tienda de Home Assistant."
    entries = newer_entries(parse_changelog(text), reported_installed) if text else []
    if text:
        latest = max(latest, latest_version(parse_changelog(text), latest), key=version_tuple)
        update_available = version_gt(latest, reported_installed)
    return ChangelogResult(
        installed_version=reported_installed,
        latest_version=latest,
        entries=entries,
        update_available=update_available,
        source="supervisor",
        checked=True,
        full_changelog_url=FULL_CHANGELOG_URL,
        error=error,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


async def get_changelog() -> ChangelogResult:
    installed_version = APP_VERSION
    supervisor_result = await _try_supervisor(installed_version)
    if supervisor_result is not None:
        return supervisor_result

    error: str | None = None
    try:
        text = await _fetch_remote()
        entries = parse_changelog(text)
        latest = latest_version(entries, installed_version)
        return ChangelogResult(
            installed_version=installed_version,
            latest_version=latest,
            entries=newer_entries(entries, installed_version),
            update_available=version_gt(latest, installed_version),
            source="github",
            checked=True,
            full_changelog_url=FULL_CHANGELOG_URL,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        error = "No se ha podido consultar el changelog en GitHub."

    text = _read_local()
    if text:
        entries = parse_changelog(text)
        latest = latest_version(entries, installed_version)
        return ChangelogResult(
            installed_version=installed_version,
            latest_version=latest,
            entries=newer_entries(entries, installed_version),
            update_available=version_gt(latest, installed_version),
            source="local",
            checked=False,
            full_changelog_url=FULL_CHANGELOG_URL,
            error=error,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    return ChangelogResult(
        installed_version=installed_version,
        latest_version=installed_version,
        entries=[],
        update_available=False,
        source="local",
        checked=False,
        full_changelog_url=FULL_CHANGELOG_URL,
        error=error or "No hay changelog disponible.",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
