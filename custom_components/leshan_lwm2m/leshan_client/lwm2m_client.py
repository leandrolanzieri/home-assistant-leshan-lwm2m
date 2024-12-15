"""A LwM2M client at the Leshan server."""

from dataclasses import dataclass

from .objects import Lwm2mObjectInstance


@dataclass
class Lwm2mClient:
    """A LwM2M client at the Leshan server."""

    endpoint: str
    "The endpoint name of the client."

    registration_id: str
    "The registration ID of the client."

    registration_timestamp: int
    "The timestamp of the client's registration."

    last_update_timestamp: int
    "The timestamp of the client's last update."

    address: str
    "The address of the client."

    version: str
    "The firmware version of the client."

    lifetime: int
    "The lifetime of the client."

    binding_mode: str
    "The binding mode of the client."

    root_path: str
    "The root path of the client."

    secure: bool
    "Whether the connection to the client is secure."

    object_instances: list[Lwm2mObjectInstance]
    "The object instances of the client."

    def __post_init__(self) -> None:
        """Initialize the object instances after the dataclass is created."""
        object_instances = []

        for obj_id, instances in self.object_instances.items():  # type: ignore[attr-defined]
            obj_id_int = int(obj_id)
            object_instances.extend(
                Lwm2mObjectInstance(obj_id_int, instance_id)
                for instance_id in instances
            )

        self.object_instances = object_instances

    def __eq__(self, value: object) -> bool:
        """Check if two Lwm2mClient instances are equal based on their endpoint."""
        return isinstance(value, Lwm2mClient) and value.endpoint == self.endpoint
