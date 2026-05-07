# Blustream Device Control Library and CLI

Python library and command-line tool for controlling Blustream audio devices, starting with the DMP168 digital audio matrix processor.

## Features

- **Library API**: Clean Python API for programmatic device control
- **CLI Tool**: Command-line interface for device management
- **Extensible**: Architecture supports multiple Blustream device types
- **TCP/IP Communication**: Network-based device control

## Installation

```bash
pip install -e .
```

Or install in development mode:

```bash
pip install -e ".[dev]"
```

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

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Future Enhancements

See [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) for planned features and improvements.

