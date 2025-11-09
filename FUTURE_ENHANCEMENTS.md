# Future Enhancements

This document tracks planned future enhancements to the Bluestream device control library and CLI.

## Command Metadata System

**Current State**: Simple command registry with name -> builder function mapping

**Future Enhancement**: Full command metadata system with:
- `Command` dataclass: name, description, parameters, return_type, handler, requires_confirmation
- `Parameter` dataclass: name, type, required, default, choices, help_text, validation, depends_on
- Command parameter dependencies (conditional parameters)
- Parameter validation rules
- Command aliases support

**Benefits**:
- Enables fully dynamic CLI generation
- Self-documenting commands
- Better type checking and validation
- Automatic help text generation

**Implementation Notes**:
- Can be added incrementally
- Start with basic metadata (name, description, parameters)
- Add advanced features (dependencies, validation) later
- Maintain backward compatibility with simple registry

## Dynamic CLI Generation

**Current State**: Manual CLI command definitions for each command

**Future Enhancement**: Fully dynamic CLI that:
- Introspects device commands via metadata
- Generates argparse subcommands and arguments automatically
- Handles conditional parameters based on dependencies
- Auto-generates help text from command metadata
- Supports command aliases

**Benefits**:
- No hardcoded CLI commands
- Adding new device commands automatically extends CLI
- Consistent CLI interface across devices
- Less maintenance overhead

**Implementation Notes**:
- Requires command metadata system first
- May need to switch from argparse to click for better dynamic support
- Consider hybrid approach: metadata-driven with manual overrides

## Telnet Protocol Support

**Current State**: Raw TCP with Telnet negotiation byte filtering

**Future Enhancement**: Full Telnet protocol support:
- Proper Telnet negotiation handling
- Support for Telnet options (echo, line mode, etc.)
- Better handling of special Telnet sequences
- Support for devices that require full Telnet compliance

**Implementation Notes**:
- Python's `telnetlib` is deprecated in 3.13+
- Consider third-party library like `telnetlib3` or `pytelnet`
- Or implement minimal Telnet negotiation ourselves
- Current approach (filtering bytes) works for DMP168 but may not for all devices

## Async/Await Support

**Current State**: Synchronous operations only

**Future Enhancement**: Async/await support for:
- Non-blocking device operations
- Concurrent command execution
- Better integration with async frameworks
- Async context manager support

**Implementation Notes**:
- Would require async connection implementation
- Consider `asyncio` and `aiohttp` or `asyncio` sockets
- Maintain synchronous API for backward compatibility
- Add async methods alongside sync methods

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
- Config file location: `~/.bluestream/config.yaml`, `./bluestream.yaml`

**Implementation Notes**:
- Optional dependency (PyYAML if using YAML)
- Precedence: CLI > config file > env vars > defaults
- Support multiple config file formats
- Document configuration schema

## Device Version Detection

**Current State**: No version detection

**Future Enhancement**: Device version detection:
- Query device firmware version
- Command availability based on version
- Version-specific command implementations
- Compatibility checking

**Implementation Notes**:
- DMP168 returns version in STATUS response
- Can use this to determine available commands
- May need version-specific parsers
- Document version compatibility

## Advanced Error Handling

**Current State**: Basic error handling

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

**Current State**: Basic test structure planned

**Future Enhancement**: Comprehensive testing:
- Test dynamic CLI builder
- Test error conditions and edge cases
- Test response parsing edge cases
- Performance testing
- Integration test fixtures
- Mock device server for testing

**Implementation Notes**:
- Create comprehensive test fixtures
- Mock device that responds like real device
- Test all error paths
- Consider property-based testing

## Documentation Enhancements

**Current State**: Basic README and docstrings planned

**Future Enhancement**: Comprehensive documentation:
- API reference documentation (Sphinx)
- Tutorials and examples
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

**Future Enhancement**: Support additional Bluestream devices:
- DMP168X (if different from DMP168)
- Other Bluestream audio matrix processors
- Common command patterns across devices
- Device-specific command implementations

**Implementation Notes**:
- Architecture already supports multiple devices
- Each device in its own directory
- Share common patterns where possible
- Document device differences

## Command Aliases

**Current State**: No alias support

**Future Enhancement**: Command aliases:
- Short command names (e.g., "vol" -> "volume")
- Device-specific aliases
- User-configurable aliases
- Alias resolution in CLI and library

**Implementation Notes**:
- Add to command metadata
- Support in command registry
- CLI should show aliases in help
- Library should accept aliases

## Increment/Decrement Operations

**Current State**: Absolute value setting only

**Future Enhancement**: Relative operations:
- Support for "+" and "-" values (increment/decrement)
- Relative volume changes
- Step-based adjustments
- Smart defaults for step sizes

**Implementation Notes**:
- DMP168 API supports "+" and "-" for relative changes
- Need special handling in parameter validation
- Consider convenience methods in library API

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

