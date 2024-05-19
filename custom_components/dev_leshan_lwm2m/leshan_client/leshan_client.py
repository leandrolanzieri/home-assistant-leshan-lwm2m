"""Asynchronous Leshan client for Python."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypedDict
import aiohttp
import json
import logging

from yarl import URL

from .lwm2m_resource_value import Lwm2mResourceValue
from .lwm2m_client import Lwm2mClient
from .exceptions import (
    LeshanClientError,
    LeshanClientEmptyResponseError,
    LeshanClientConnectionError,
    LeshanClientConnectionTimeoutError,
)

from aiohttp_sse_client import client as sse_client

_LOGGER = logging.getLogger(__name__)

class _Callback(TypedDict):
    endpoint: str
    object_id: int
    instance_id: int
    resource_id: int
    callback: Callable[[Lwm2mResourceValue], Awaitable[None]]

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
        self.host = host
        self.request_timeout = request_timeout
        self.session = session
        self.loop = asyncio.get_event_loop()
        self.obs_callbacks: list[_Callback] = []

    async def _listen_endpoint_notifications(self, endpoint: str):
        """
        Listen for notifications from a LwM2M client.

        Args:
            endpoint: The endpoint of the client to listen for notifications from.
        """
        path = f"{self.API_PATH}/event?ep={endpoint}"
        uri = f"http://{self.host}{path}"

        while True:
            try:
                async with sse_client.EventSource(uri) as event_source:
                    _LOGGER.debug(f"Listening for notifications from {endpoint}")
                    try:
                        async for event in event_source:
                            if event.type != "NOTIFICATION":
                                _LOGGER.debug(f"Ignoring event type {event.type} from {endpoint}")
                                continue

                            data = json.loads(event.data)
                            _LOGGER.debug(f"Received notification from {endpoint}: {data}")

                            for callback in self.obs_callbacks:
                                callback_res = f"/{callback['object_id']}/{callback['instance_id']}/{callback['resource_id']}"
                                if callback["endpoint"] == data["ep"] and callback_res in data["res"]:
                                    value = Lwm2mResourceValue(
                                        resource_id=data["val"]["id"],
                                        type=data["val"]["type"],
                                        value=data["val"]["value"],
                                    )
                                    await callback["callback"](value)

                    except ConnectionError:
                        pass
            except Exception as e:
                _LOGGER.error(f"Error listening for notifications from {endpoint}: {e}")
                _LOGGER.debug(f"Retrying in 5 seconds")
                await asyncio.sleep(5)

    async def list_clients(self) -> list[Lwm2mClient]:
        """
        List all LwM2M clients.

        Returns:
            A list of clients.

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
            clients.append(client)

        return clients

    async def read(self, endpoint: str, object_id: int, instance_id: int,
                   resource_id: int=None) -> list[Lwm2mResourceValue]:
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
        url = URL.build(scheme="http", host=self.host, path=uri)

        headers = {
            "Accept": "application/json, text/plain, */*",
        }

        # if no session, create one
        if self.session is None:
            self.session = aiohttp.ClientSession()

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.request(
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
            message = f"Timeout connecting to server at {self.host}"
            raise LeshanClientConnectionTimeoutError(message) from e

        except aiohttp.ClientConnectionError as e:
            message = f"Error connecting to server at {self.host}"
            raise LeshanClientConnectionError(message) from e

    async def observe(self, endpoint: str, object_id: int, instance_id: int, resource_id: int, callback: Callable[[any], Awaitable[None]]):
        """
        Observe a resource from a LwM2M client.

        Args:
            object_id: The object ID.
            instance_id: The instance ID.
            resource_id: The resource ID.

        Raises:
            LeshanClientEmptyResponseError: If the server returns an empty response.
            LesanClientError: If the server returns an error.
            LesanClientConnectionError: If there is an error connecting to the server.
            LesanClientConnectionTimeoutError: If the connection to the server times out.
        """
        # add callback to list
        cb = {
            "endpoint": endpoint,
            "object_id": object_id,
            "instance_id": instance_id,
            "resource_id": resource_id,
            "callback": callback,
        }

        try:
            # check if we are already listening for notifications on this endpoint
            if not any(cb["endpoint"] == endpoint for cb in self.obs_callbacks):
                self.loop.create_task(self._listen_endpoint_notifications(endpoint))
        except Exception as e:
            _LOGGER.error(f"Failed to listen for notifications from {endpoint}: {e}")

        self.obs_callbacks.append(cb)

        try:
            await self.request(f"{self.API_CLIENTS_PATH}/{endpoint}/{object_id}/{instance_id}/{resource_id}/observe", method="POST")
        except LeshanClientError as e:
            _LOGGER.error(f"Failed to observe resource {resource_id} on {endpoint}: {e}")
        except Exception as e:
            _LOGGER.error(f"Failed to observe resource {resource_id} on {endpoint}: {e}")

    async def close(self):
        """
        Close the client session.
        """
        if self.session:
            await self.session.close()
            self.session = None
