from abc import ABC
from typing import ClassVar, Self


class BaseRegistry[T, V](ABC):
    _instance: ClassVar[Self | None] = None
    _registry: dict[T, V]

    def __new__(cls: type[Self]) -> Self:
        if cls._instance is None:
            inst = super().__new__(cls)
            if not hasattr(inst, "_registry"):
                inst._registry = {}  # type: ignore[assignment]
            cls._instance = inst

        return cls._instance

    def register(self, key: T, value: V) -> None:
        self._registry[key] = value

    def get_class(self, key: T) -> V:
        if key not in self._registry:
            raise ValueError(f"Unknown object type: {key}, needed: {self._registry.keys()}")
        return self._registry[key]

    def get_all_types(self) -> dict[T, V]:
        return self._registry.copy()

    def is_registered(self, key: T) -> bool:
        return key in self._registry
