"""A simple representation of a LwM2M object."""

from dataclasses import dataclass

@dataclass
class Lwm2mObjectInstance:
    object_id: int
    instance_id: dict

    def __post_init__(self):
        self.object_id = int(self.object_id)

