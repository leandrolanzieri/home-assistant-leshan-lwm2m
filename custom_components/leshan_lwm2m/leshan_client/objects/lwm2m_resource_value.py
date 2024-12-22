"""Module for defining LwM2M resource values and their types."""

from __future__ import annotations

from dataclasses import dataclass

# enum for the type of the resource value
from enum import StrEnum, auto


class Lwm2mResourceValueType(StrEnum):
    """Enum for the type of the LwM2M resource value."""

    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    OPAQUE = auto()
    TIME = auto()
    OBJLNK = auto()


@dataclass
class Lwm2mResourceValue:
    """Class representing a LwM2M resource value."""

    resource_id: int
    type: Lwm2mResourceValueType
    value: str | int | float | bool | bytes

    def __post_init__(self) -> None:
        """Post-initialization processing to ensure the correct type of the value."""
        self.type = Lwm2mResourceValueType(self.type.lower())
        if self.type == Lwm2mResourceValueType.INTEGER:
            self.value = int(self.value)
        elif self.type == Lwm2mResourceValueType.FLOAT:
            self.value = float(self.value)
        elif self.type == Lwm2mResourceValueType.BOOLEAN:
            self.value = bool(self.value)
