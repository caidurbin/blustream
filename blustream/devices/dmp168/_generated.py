"""Generated wire-protocol formatters for the dmp168.

DO NOT EDIT. Regenerate with: python -m spec.codegen.emit_python
Source: spec/protocol.yaml
Spec hash: 620b0eefa790c78d
Device: Blustream dmp168
Firmware baseline: 1.5.0
"""

DEFAULT_PORT = 8000
ALTERNATIVE_PORT = 23
TERMINATOR = '\r\n'



def format_power_on() -> str:
    """Power the device on."""
    return 'PON'

