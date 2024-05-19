"""A LwM2M client at the Leshan server."""

from dataclasses import dataclass
from .lwm2m_object_instance import Lwm2mObjectInstance

@dataclass
class Lwm2mClient:
    endpoint: str
    registration_id: str
    registration_timestamp: int
    last_update_timestamp: int
    address: str
    version: str
    lifetime: int
    binding_mode: str
    root_path: str
    secure: bool
    object_instances: list[Lwm2mObjectInstance]

    def __post_init__(self):
        object_instances = []
        for obj_id, instances in self.object_instances.items():
            for instance_id in instances:
                object_instances.append(Lwm2mObjectInstance(obj_id, instance_id))

        self.object_instances = object_instances
