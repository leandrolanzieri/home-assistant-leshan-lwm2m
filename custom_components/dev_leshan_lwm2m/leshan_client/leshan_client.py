"""Asynchronous Leshan client for Python."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import aiohttp
import json
import logging

from yarl import URL
from typing import Awaitable, Callable
from aiohttp_sse_client import client as sse_client

from .exceptions import (
    LeshanClientError,
    LeshanClientEmptyResponseError,
    LeshanClientConnectionError,
    LeshanClientConnectionTimeoutError,
)
from .lwm2m_client import Lwm2mClient, Lwm2mObjectInstance
from .objects import Lwm2mResourceValue

_LOGGER = logging.getLogger(__name__)

@dataclass
class ObservationEntry:
    """
    An observation entry to keep track of the resources being observed.
    """
    client: Lwm2mClient
    "The client of the resource being observed."

    instance: Lwm2mObjectInstance
    "The instance of the resource being observed."

    resource_id: int
    "The resource ID of the resource being observed."

    callback: Callable[[LeshanClient, Lwm2mObjectInstance, Lwm2mResourceValue], Awaitable[None]]
    "The callback to call when the resource changes."


class LeshanClient:
    """
    Leshan client for interacting with LwM2M clients.

    Args:
        host: The host of the Leshan server.
        request_timeout: The timeout for requests to the server.
        session: An aiohttp session to use for requests. If None, a new session is created.
    """
    API_PATH = "/api"
    API_CLIENTS_PATH = f"{API_PATH}/clients"

    def __init__(self, host: str, request_timeout: float = 5.0, session: aiohttp.ClientSession | None = None):
        self._host = host
        self._request_timeout = request_timeout
        self._session = session
        self._endpoint_notification_tasks: dict[str, asyncio.Task] = {}
        self._endpoint_notification_stop_events: dict[str, asyncio.Event] = {}
        self._observations: list[ObservationEntry] = []

        self.lwm2m_clients: list[Lwm2mClient] = []
        """The LwM2M clients registered with the Leshan server."""

    async def _listen_endpoint_notifications(self, endpoint: str, stop_event: asyncio.Event):
        """
        Listen for notifications from a LwM2M client.

        Args:
            endpoint: The endpoint of the client to listen for notifications from.
            stop_event: The event to stop listening for notifications.
        """
        path = f"{self.API_PATH}/event?ep={endpoint}"
        uri = f"http://{self._host}{path}"

        while not stop_event.is_set():
            try:
                async with sse_client.EventSource(uri) as event_source:
                    _LOGGER.debug(f"Listening for notifications on {endpoint}")
                    async for event in event_source:
                        if event.type != "NOTIFICATION":
                            _LOGGER.debug(f"Ignoring event type {event.type} from {endpoint}")
                            continue

                        data = json.loads(event.data)
                        _LOGGER.debug(f"Received notification from {endpoint}: {data}")

                        resource_parts = data["res"].split("/")
                        object_id = int(resource_parts[1])
                        instance_id = int(resource_parts[2])
                        resource_id = int(resource_parts[3])

                        value = Lwm2mResourceValue(
                            resource_id=data["val"]["id"],
                            type=data["val"]["type"],
                            value=data["val"]["value"],
                        )


                        for observation in self._observations:
                            if observation.client.endpoint == data["ep"] and \
                                    observation.instance.object_id == object_id and \
                                    observation.instance.instance_id == instance_id and \
                                    observation.resource_id == resource_id:

                                await observation.callback(
                                    observation.client,
                                    observation.instance,
                                    value
                                )
            except TimeoutError:
                pass
            except Exception as e:
                _LOGGER.error(f"Error listening for notifications on {endpoint}: {e}")
                _LOGGER.debug(f"Retrying in 5 seconds")
                await asyncio.sleep(5)

    async def listen_registrations(self, callback: Callable[[Lwm2mClient], Awaitable[None]]):
        """
        Listen for new client registrations.

        Args:
            callback: The callback to call when a new client is registered.
        """
        path = f"{self.API_PATH}/event"
        uri = f"http://{self._host}{path}"

        while True:
            try:
                async with sse_client.EventSource(uri) as event_source:
                    _LOGGER.debug("Listening for registrations")
                    async for event in event_source:
                        if event.type != "REGISTRATION":
                            _LOGGER.debug(f"Ignoring event type {event.type}")
                            continue

                        data = json.loads(event.data)
                        _LOGGER.debug(f"Received registration: {data}")

                        client = Lwm2mClient(
                            endpoint=data["endpoint"],
                            registration_id=data["registrationId"],
                            registration_timestamp=data["registrationDate"],
                            last_update_timestamp=data["lastUpdate"],
                            address=data["address"],
                            version=data["lwM2mVersion"],
                            lifetime=data["lifetime"],
                            binding_mode=data["bindingMode"],
                            root_path=data["rootPath"],
                            secure=data["secure"],
                            object_instances=data["availableInstances"],
                        )

                        await callback(client)
            except TimeoutError as e:
                pass

            except Exception as e:
                _LOGGER.error(f"Error listening for registrations: {e}")
                _LOGGER.debug(f"Retrying in 5 seconds")
                await asyncio.sleep(5)

    async def test_server(self):
        """
        Test the connection to the Leshan server. The method raises an exception if the connection fails.

        Raises:
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
            LeshanClientEmptyResponseError: If the server returns an empty response.
        """
        response = await self.request(self.API_CLIENTS_PATH)
        if response is None:
            raise LeshanClientEmptyResponseError("Empty response from server")

    async def get_clients(self) -> list[Lwm2mClient]:
        """
        Get the list of LwM2M clients registered with the Leshan server.

        Returns:
            The list of LwM2M clients.

        Raises:
            LeshanClientEmptyResponseError: If the server returns an empty response.
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
        """
        response = await self.request(self.API_CLIENTS_PATH)
        clients = []
        for client_data in response:
            client = Lwm2mClient(
                endpoint=client_data["endpoint"],
                registration_id=client_data["registrationId"],
                registration_timestamp=client_data["registrationDate"],
                last_update_timestamp=client_data["lastUpdate"],
                address=client_data["address"],
                version=client_data["lwM2mVersion"],
                lifetime=client_data["lifetime"],
                binding_mode=client_data["bindingMode"],
                root_path=client_data["rootPath"],
                secure=client_data["secure"],
                object_instances=client_data["availableInstances"],
            )

            for existing_client in self.lwm2m_clients:
                if existing_client.endpoint == client.endpoint:
                    break
            else:
                self.lwm2m_clients.append(client)
                clients.append(client)

        return self.lwm2m_clients

    async def read(self, endpoint: str, object_id: int, instance_id: int,
                   resource_id: int = None) -> list[Lwm2mResourceValue]:
        """
        Read a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            resource_id: The resource ID. If None, all resources are read.

        Returns:
            The resource value.

        Raises:
            LeshanClientEmptyResponseError: If the server returns an empty response.
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
        """
        uri = f"{self.API_CLIENTS_PATH}/{endpoint}/{object_id}/{instance_id}"
        if resource_id:
            uri += f"/{resource_id}"

        response = await self.request(uri)
        _LOGGER.debug(response)
        if response is None:
            raise LeshanClientEmptyResponseError("Empty response from server")

        values: list[Lwm2mResourceValue] = []
        if resource_id:
            values.append(Lwm2mResourceValue(
                resource_id=response["content"]["id"],
                type=response["content"]["type"],
                value=response["content"]["value"],
            ))
        else:
            for resource in response["content"]["resources"]:
                values.append(Lwm2mResourceValue(
                    resource_id=resource["id"],
                    type=resource["type"],
                    value=resource["value"],
                ))

        return values

    async def write(self, endpoint: str, object_id: int, instance_id: int, values: list[Lwm2mResourceValue]):
        """
        Write a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            values: The values to write.

        Raises:
            LeshanClientEmptyResponseError: If the server returns an empty response.
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
        """
        uri = f"{self.API_CLIENTS_PATH}/{endpoint}/{object_id}/{instance_id}"

        data = {
            "id": instance_id,
            "kind": "instance",
            "resources": []
        }

        for value in values:
            data["resources"].append({
                "id": value.resource_id,
                "kind": "singleResource",
                "type": value.type,
                "value": value.value,
            })

        response = await self.request(uri, method="PUT", data=data)
        if response is None:
            raise LeshanClientEmptyResponseError("Empty response from server")

    async def request(self, uri: str = "", method: str = "GET", data: dict | None = None):
        """
        Make an HTTP request to the Leshan server.

        Args:
            uri: The URI to request.
            method: The HTTP method to use.
            data: The data to send with the request.

        Returns:
            The response from the server as a python dict.

        Raises:
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
        """
        url = URL.build(scheme="http", host=self._host, path=uri)

        headers = {
            "Accept": "application/json, text/plain, */*",
        }

        # if no session, create one
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            async with asyncio.timeout(self._request_timeout):
                response = await self._session.request(
                    method,
                    url,
                    json=data,
                    headers=headers,
                )

            content_type = response.headers.get("Content-Type", "")
            if response.status >= 400 and response.status < 600:
                content = await response.read()
                response.close()

                if content_type == "application/json":
                    content = json.loads(content.decode("utf-8"))
                    raise LeshanClientError(response.status, content)

                raise LeshanClientError(
                    response.status,
                    {"message": content.decode("utf-8")},
                )

            if content_type == "application/json":
                return await response.json()

            return await response.text()

        except asyncio.TimeoutError as e:
            message = f"Timeout connecting to server at {self._host}"
            raise LeshanClientConnectionTimeoutError(message) from e

        except aiohttp.ClientConnectionError as e:
            message = f"Error connecting to server at {self._host}"
            raise LeshanClientConnectionError(message) from e

    async def observe(self, client: Lwm2mClient, instance: Lwm2mObjectInstance, resource_id: int, callback: Callable[[Lwm2mResourceValue], Awaitable[None]]):
        """
        Observe a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            resource_id: The resource ID.
            callback: The callback to call when the resource changes.
        """
        obs_entry = ObservationEntry(
            client=client,
            instance=instance,
            resource_id=resource_id,
            callback=callback,
        )

        loop = asyncio.get_event_loop()

        try:
            # leshan will trigger notifications per endpoint, not per resource or object
            # check if we are already listening for notifications on this endpoint
            if not any(obs.client.endpoint == obs_entry.client.endpoint for obs in self._observations):
                stop_event = asyncio.Event()
                self._endpoint_notification_stop_events[obs_entry.client.endpoint] = stop_event

                task = loop.create_task(self._listen_endpoint_notifications(obs_entry.client.endpoint, stop_event))
                self._endpoint_notification_tasks[obs_entry.client.endpoint] = task
        except Exception as e:
            _LOGGER.error(f"Failed to listen for notifications from {obs_entry.client}: {e}")

        self._observations.append(obs_entry)
        await self._observe_resource(
            client=obs_entry.client,
            instance=obs_entry.instance,
            resource_id=obs_entry.resource_id,
        )

    async def cancel_observe(self, client: Lwm2mClient, instance: Lwm2mObjectInstance, resource_id: int):
        """
        Cancel observing a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            resource_id: The resource ID.
        """
        # find the observation entry
        obs_entry = None
        for obs in self._observations:
            if obs.client.endpoint == client.endpoint and \
                    obs.instance.object_id == instance.object_id and \
                    obs.instance.instance_id == instance.instance_id and \
                    obs.resource_id == resource_id:
                obs_entry = obs
                break
        else:
            return

        await self._cancel_observe(client, instance, resource_id)
        self._observations.remove(obs_entry)

        # cancel the endpoint notification task if there are no more observations for this endpoint
        if not any(obs.client.endpoint == obs_entry.client.endpoint for obs in self._observations):
            stop_event = self._endpoint_notification_stop_events.pop(obs_entry.client.endpoint)
            stop_event.set()

            task = self._endpoint_notification_tasks.pop(obs.client.endpoint)
            task.cancel()


    async def _cancel_observe(self, client: Lwm2mClient, instance: Lwm2mObjectInstance, resource_id: int):
        """
        Actively cancel observing a resource from a LwM2M client.

        Args:
            client: The client to cancel the observe on.
            instance: The instance to cancel the observe on.
            resource_id: The resource ID to cancel the observe on.
        """
        path = f"{self.API_CLIENTS_PATH}"
        path += f"/{client.endpoint}/{instance.object_id}/{instance.instance_id}/{resource_id}"
        path += "/observe?active"

        try:
            await self.request(path, method="DELETE")
        except LeshanClientError as e:
            _LOGGER.error(f"Failed to cancel observe {path}: {e}")
        except Exception as e:
            _LOGGER.error(f"Failed to cancel observe {path}: {e}")

    async def _observe_resource(self, client: Lwm2mClient, instance: Lwm2mObjectInstance, resource_id: int):
        """
        Observe a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            resource_id: The resource ID.
        """
        path = f"{self.API_CLIENTS_PATH}"
        path += f"/{client.endpoint}/{instance.object_id}/{instance.instance_id}/{resource_id}"
        path += "/observe"

        try:
            await self.request(path, method="POST")
        except LeshanClientError as e:
            _LOGGER.error(f"Failed to observe {path}: {e}")
        except Exception as e:
            _LOGGER.error(f"Failed to observe {path}: {e}")


    async def close(self):
        """
        Close the client session.
        """
        if self._session:
            await self._session.close()
            self._session = None
