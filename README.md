# Blustream

Open-source toolkit for controlling [Blustream](https://www.blustream.com/) audio
devices — starting with the DMP168 digital audio matrix processor — across
three home-automation surfaces.

## Components

This repository is a monorepo housing three deliverables that share a single
protocol contract under `spec/`:

1. **Python library + CLI** (`blustream/`). A clean async Python API and a
   `blustream` console script. Ships to **[PyPI](https://pypi.org/project/blustream/)**
   on `v*` tags.
2. **Control4 driver** (`control4/dmp168/`). A Lua driver packaged as a
   `.c4z` archive that exposes the matrix as a standard Control4 audio
   matrix. Ships as a **GitHub release** with the `.c4z` attached on
   `c4-v*` tags.
3. **Home Assistant integration** (`custom_components/blustream/`). The
   directory is reserved and registered with HACS; the integration code
   itself is deferred to a future PRD. The eventual integration will depend
   on the published `blustream` PyPI library rather than re-embedding the
   protocol code.

The protocol primitives shared between the library and the driver are
**generated** from `spec/protocol.yaml` via the codegen tooling under
`spec/codegen/`. The Python and Lua emitters write into
`blustream/devices/dmp168/_generated.py` and
`control4/dmp168/src/generated.lua` respectively, and CI fails when those
committed files drift from what the spec would produce.

## Independent versioning

Each component releases on its own cadence using a distinct tag prefix. The
prefixes are disjoint so a tag for one component cannot accidentally trigger
the wrong release workflow.

| Component       | Tag prefix | Workflow                                | Artifact                                 |
| --------------- | ---------- | --------------------------------------- | ---------------------------------------- |
| Python library  | `v*`       | `.github/workflows/release-pypi.yml`    | `blustream` on PyPI (sdist + wheel)      |
| Control4 driver | `c4-v*`    | `.github/workflows/release-c4z.yml`     | GitHub release with attached `.c4z`      |
| HA integration  | _reserved_ | _deferred_                              | _deferred_ (will use HACS once built)    |

For example, a library bug-fix release tags `v0.2.1`, while a driver-only
update tags `c4-v0.3.0`. The shared `spec/` directory is the coordination
point when a protocol change requires both components to move in lockstep.

## Installation

### Python library + CLI

Once published, the library installs from PyPI:

```bash
pip install blustream
```

For local development from a checkout:

```bash
pip install -e ".[dev]"
```

### Control4 driver

Download the `.c4z` from the latest [GitHub release](https://github.com/caidurbin/blustream/releases)
tagged `c4-v*` and install it through Composer Pro. See
`docs/control4-driver-plan.md` for the dealer-load workflow.

## Library Usage

```python
import asyncio
from blustream import DMP168

async def main():
    # Connect to device
    device = DMP168(host='192.168.1.100', port=23)
    await device.connect()

    # Read status
    status = await device.get_status()
    print(f"Temperature: {status.temperature}°C")
    print(f"DSP Usage: {status.dsp_usage}%")

    # Control device
    await device.power_on()
    await device.set_output_volume(1, 75, unit='percent')
    await device.route_input_to_output(input_ch=2, output=1)

    # Context manager support
    async with DMP168(host='192.168.1.100') as device:
        status = await device.get_status()
        await device.power_on()

    # Disconnect
    await device.disconnect()

# Run the async function
asyncio.run(main())
```

## CLI Usage

Subcommand names are derived from the command registry. Use `blustream --help`
to list all commands and `blustream <command> --help` for parameter details.

### Get Device Status

```bash
blustream --host 192.168.1.100 status
```

### Power Control

```bash
blustream --host 192.168.1.100 power-on
blustream --host 192.168.1.100 power-off
```

### Volume Control

```bash
# Set output 1 volume to 75%
blustream --host 192.168.1.100 output-volume --output 1 --level 75

# Set output 1 volume to -10 dB
blustream --host 192.168.1.100 output-volume --output 1 --level -10 --unit dB

# Increase output 1 volume by one step
blustream --host 192.168.1.100 output-volume --output 1 --increase-level

# Decrease output 1 volume by one step
blustream --host 192.168.1.100 output-volume --output 1 --decrease-level
```

### Mute Control

```bash
# Mute output 1
blustream --host 192.168.1.100 output-mute --output 1 --mute

# Unmute output 1
blustream --host 192.168.1.100 output-mute --output 1 --no-mute
```

### Routing

```bash
# Route input 2 to output 1
blustream --host 192.168.1.100 route --input 2 --output 1
```

### Presets

```bash
# Save current configuration to preset 1
blustream --host 192.168.1.100 preset-save --preset 1

# Recall preset 1
blustream --host 192.168.1.100 preset-recall --preset 1

# Get preset status
blustream --host 192.168.1.100 preset-status --preset 1
```

### JSON Output

```bash
# Get status as JSON
blustream --host 192.168.1.100 status --json
```

## Command Line Options

Global flags must appear **before** the subcommand (e.g. `blustream --yes reboot`, not `blustream reboot --yes`).

- `--device`: Device type (default: dmp168)
- `--host`: Device hostname or IP address (default: localhost)
- `--port`: TCP port (default: 23)
- `--timeout`: Connection timeout in seconds (default: 5.0)
- `--verbose`, `-v`: Enable verbose output
- `--debug`: Enable debug output
- `--json`: Output results as JSON
- `--yes`, `-y`: Skip confirmations

## Architecture

The library is designed with extensibility in mind:

- **Base Framework**: Abstract base classes for devices and connections
- **Device Implementations**: Device-specific code in separate modules
- **Command Registry**: Commands are registered with metadata for introspection
- **Connection Layer**: Pluggable connection implementations (TCP/IP, serial, etc.)

## Supported Devices

- **DMP168**: Digital audio matrix processor (16 inputs, 8 outputs)

## Development

### Project Structure

```
blustream/
├── blustream/              # Main package
│   ├── base/                # Base classes and interfaces
│   ├── connection/          # Connection implementations
│   ├── devices/             # Device-specific implementations
│   │   └── dmp168/          # DMP168 device
│   └── cli/                 # CLI implementation
├── tests/                   # Test suite
├── main.py                  # CLI entry point
├── setup.py                 # Package setup
└── README.md               # This file
```

### Running Tests

```bash
pytest tests/
```

### Lua development

The Control4 driver lives under `control4/` and targets Lua 5.1 (the version
the Control4 Composer sandbox runs). CI lints all Lua sources with
[`luacheck`](https://github.com/lunarmodules/luacheck) and runs the unit
tests with [`busted`](https://lunarmodules.github.io/busted/) — see
[`.github/workflows/lua.yml`](.github/workflows/lua.yml).

To install the toolchain locally:

```bash
# macOS
brew install lua@5.1 luarocks
luarocks --lua-version=5.1 install luacheck
luarocks --lua-version=5.1 install busted

# Debian / Ubuntu
sudo apt-get install lua5.1 liblua5.1-0-dev luarocks
sudo luarocks --lua-version=5.1 install luacheck
sudo luarocks --lua-version=5.1 install busted
```

Then, from the repo root:

```bash
luacheck .                              # lint all Lua source
busted --pattern=_spec control4/        # run Lua unit tests
```

## License

This project is licensed under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Future Enhancements

See [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) for planned features and improvements.

