# Home Assistant integration

A local-polling Home Assistant integration for the Inowattio's Nemesis controller.

## Features

- Zeroconf auto-discovery (`_nemesis._tcp.local.`) plus manual host/port setup.
- Polls the controller every 3 seconds over HTTP (`/status` and `/data`).
- Exposes sensors for:
  - **Grid power** (W)
  - **Controller state**
  - **IP address**, **API protocol**, **Unit name**, **Unit ID**, **Software version** (diagnostic)

## Requirements

- Home Assistant `2026.4.3` or newer.
- A Nemesis controller reachable on your LAN (default port `6969`).

## Installation

### HACS (recommended)

1. Add this repository as a custom integration repository in HACS.
2. Install **Inowattio** from the HACS integrations list.
3. Restart Home Assistant.

### Manual

1. Copy `custom_components/inowattio/` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

Go to **Settings → Devices & Services → Add Integration → Inowattio**. If the controller is on the same network it will usually be auto-discovered; otherwise enter its host/IP and port manually.

## License

See the repository for license details.
