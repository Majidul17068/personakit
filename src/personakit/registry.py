"""SpecialistRegistry — for apps that juggle many specialists.

Common pattern: a product hosts dozens of specialists (fall, medication, legal
contract, equity analysis, tutor) and routes incoming cases to the right one by
`name` or `domain` tag.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .errors import RegistryError
from .loaders import specialist_from_json, specialist_from_yaml
from .specialist import Specialist


class SpecialistRegistry:
    """A simple name → Specialist map with convenience loaders."""

    def __init__(self) -> None:
        self._items: dict[str, Specialist] = {}

    def register(self, specialist: Specialist, *, override: bool = False) -> None:
        if specialist.name in self._items and not override:
            raise RegistryError(
                f"A specialist named {specialist.name!r} is already registered. "
                "Pass override=True to replace it."
            )
        self._items[specialist.name] = specialist

    def unregister(self, name: str) -> None:
        self._items.pop(name, None)

    def get(self, name: str) -> Specialist:
        try:
            return self._items[name]
        except KeyError as exc:
            raise RegistryError(f"No specialist named {name!r}.") from exc

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._items

    def __iter__(self) -> Iterator[Specialist]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def names(self) -> list[str]:
        return sorted(self._items)

    def by_domain(self, domain: str) -> list[Specialist]:
        """Return all specialists whose `domain` starts with the given prefix."""
        return [s for s in self._items.values() if s.domain and s.domain.startswith(domain)]

    @classmethod
    def from_directory(cls, path: str | Path) -> SpecialistRegistry:
        """Load every `*.yaml`, `*.yml`, and `*.json` file in `path`."""
        directory = Path(path)
        if not directory.is_dir():
            raise RegistryError(f"{path} is not a directory.")
        registry = cls()
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() in {".yaml", ".yml"}:
                registry.register(specialist_from_yaml(f))
            elif f.suffix.lower() == ".json":
                registry.register(specialist_from_json(f))
        return registry
