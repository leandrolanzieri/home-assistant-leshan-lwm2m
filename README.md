# Home Assistant - LwM2M

![project-status]

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
![Project Maintenance][maintenance-shield]

_Home Assistant integration for your [LwM2M][lwm2m-doc] devices._

**This integration supports the following types of devices for now:**

Platform | LwM2M Object ID | Description |
| -- | -- | -- |
`binary_sensor` | 3342 | A read-only boolean sensor (e.g., a switch).
`light` | 3311 | Control a light status and brightness.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `leshan_lwm2m`.
1. Download _all_ the files from the `custom_components/leshan_lwm2m/` directory from this repository.
1. Place the files you downloaded in the new directory you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "LwM2M"

[lwm2m-doc]: https://www.openmobilealliance.org/lwm2m/whatis
[project-status]: https://img.shields.io/badge/Status-Work%20in%20progress!-orange?style=for-the-badge
[integration_blueprint]: https://github.com/ludeeus/integration_blueprint
[commits-shield]: https://img.shields.io/github/commit-activity/y/ludeeus/integration_blueprint.svg?style=for-the-badge
[commits]: https://github.com/leandrolanzieri/home-assistant-leshan-lwm2m/commits/main/
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/ludeeus/integration_blueprint.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Leandro%20Lanzieri-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/ludeeus/integration_blueprint.svg?style=for-the-badge
[releases]: https://github.com/ludeeus/integration_blueprint/releases
