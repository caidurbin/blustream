# Future Enhancements

This document tracks planned future enhancements to the Blustream device control library and CLI.

## Connection Pooling

**Current State**: One connection per device instance

**Future Enhancement**: Connection pooling for:
- Server/daemon use cases
- Multiple concurrent operations
- Better resource management
- Connection reuse

**Implementation Notes**:
- Useful for high-throughput scenarios
- May not be needed for typical CLI use
- Consider thread-safe connection pool implementation

## Response Caching

**Current State**: Every command sends request to device

**Future Enhancement**: Response caching for:
- STATUS and other read-only commands
- Configurable cache TTL
- Cache invalidation on write operations
- Optional caching per command type

**Implementation Notes**:
- Useful for frequently accessed status information
- Must be careful about cache invalidation
- Make it optional and configurable
- Consider cache size limits

## Batch Operations

**Current State**: One command at a time

**Future Enhancement**: Batch command execution:
- Send multiple commands in sequence
- Transaction-like operations (all or nothing)
- Rollback on error
- Command queuing

**Implementation Notes**:
- Useful for complex operations
- Must handle partial failures carefully
- Consider atomicity guarantees
- May require device support for transactions

## Configuration Management

**Current State**: CLI args, environment variables, defaults

**Future Enhancement**: Configuration file support:
- YAML/JSON/TOML config files
- Per-device configuration profiles
- Configuration validation
- Config file location: `~/.blustream/config.yaml`, `./blustream.yaml`

**Implementation Notes**:
- Optional dependency (PyYAML if using YAML)
- Precedence: CLI > config file > env vars > defaults
- Support multiple config file formats
- Document configuration schema

## Device Version Detection

**Current State**: `firmware_version` is parsed from STATUS responses but nothing is keyed off it.

**Future Enhancement**: Device version detection:
- Command availability based on version
- Version-specific command implementations
- Compatibility checking

**Implementation Notes**:
- May need version-specific parsers
- Document version compatibility

## Advanced Error Handling

**Current State**: Basic exception hierarchy (`BlustreamError`, `ConnectionError`, `TimeoutError`, `ValidationError`); no retry logic.

**Future Enhancement**: Enhanced error handling:
- Error response parsing from device
- Retry logic with exponential backoff
- Circuit breaker pattern for connection failures
- Detailed error context and diagnostics

**Implementation Notes**:
- Device may return specific error messages
- Need to parse and categorize errors
- Retry logic should be configurable
- Consider idempotent vs non-idempotent commands

## Logging Enhancements

**Current State**: Basic structured logging

**Future Enhancement**: Enhanced logging:
- Sensitive command redaction
- Log rotation and file management
- Structured logging (JSON format option)
- Performance metrics logging

**Implementation Notes**:
- Some commands (network config) are sensitive
- Consider log levels for different command types
- Support both human-readable and machine-readable logs

## Testing Enhancements

**Current State**: A broad suite under `tests/` — unit modules for the parsers, connection, and device layers, `tests/cli/` for the CLI, `tests/components/` for the HA integration, and `tests/integration/` — plus shared spec vectors exercised from both the Python and Lua sides. Coverage is being collected.

**Future Enhancement**:
- Full mock device server that speaks the wire protocol, for end-to-end tests against `TCPConnection`
- Response parsing edge cases and error-path coverage
- Performance / property-based testing

## Documentation Enhancements

**Current State**: Substantial README; docstrings present throughout the package.

**Future Enhancement**:
- API reference documentation (Sphinx)
- Tutorials and worked examples
- Architecture documentation
- Contributing guide
- Troubleshooting guide with common issues
- Device-specific documentation

**Implementation Notes**:
- Use Sphinx or similar for API docs
- Include real-world examples
- Document common pitfalls
- Keep examples up to date

## Additional Device Support

**Current State**: DMP168 only

**Future Enhancement**: Support additional Blustream devices:
- DMP168X (if different from DMP168)
- Other Blustream audio matrix processors
- Common command patterns across devices
- Device-specific command implementations

**Implementation Notes**:
- Architecture already supports multiple devices
- Each device in its own directory
- Share common patterns where possible
- Document device differences

## Interactive Command Mode

**Current State**: One command at a time

**Future Enhancement**: Interactive mode:
- REPL-like interface
- Command history
- Tab completion
- Context-aware help
- Multi-line command support

**Implementation Notes**:
- Useful for interactive debugging
- Consider using `prompt_toolkit` or `readline`
- Maintain command history
- Support both interactive and script modes
