"""A simple representation of a LwM2M object."""

from dataclasses import dataclass


@dataclass
class Lwm2mObjectInstance:
    """A class representing an instance of an LwM2M object."""

    object_id: int
    instance_id: int

    def __post_init__(self) -> None:
        """Post-initialization processing to ensure object_id is an integer."""
        self.object_id = int(self.object_id)

    def __eq__(self, value: object) -> bool:
        """Check if two Lwm2mObjectInstance objects are equal."""
        return (
            isinstance(value, Lwm2mObjectInstance)
            and value.object_id == self.object_id
            and value.instance_id == self.instance_id
        )
