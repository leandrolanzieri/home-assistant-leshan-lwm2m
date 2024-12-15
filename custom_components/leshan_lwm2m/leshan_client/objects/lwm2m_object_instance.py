"""A simple representation of a LwM2M object."""

from dataclasses import dataclass

@dataclass
class Lwm2mObjectInstance:

    object_id: int
    instance_id: int

    def __post_init__(self):
        self.object_id = int(self.object_id)

    def __eq__(self, value: object) -> bool:
        return isinstance(value, Lwm2mObjectInstance) and \
            value.object_id == self.object_id and \
            value.instance_id == self.instance_id
