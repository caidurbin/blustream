"""Response parsers for DMP168 device."""

import logging
import re
from typing import Optional

from blustream.base.exceptions import ParseError
from blustream.devices.dmp168.models import (
    InputSettings,
    OutputRouting,
    PresetStatus,
    SystemStatus,
)

logger = logging.getLogger(__name__)


class DMP168Parser:
    """Parser for DMP168 device responses."""

    @staticmethod
    def parse_status(response: str) -> SystemStatus:
        """Parse STATUS command response.

        Args:
            response: Raw STATUS response string

        Returns:
            Parsed SystemStatus object

        Raises:
            ParseError: If parsing fails
        """
        try:
            logger.debug(f"Parsing STATUS response ({len(response)} chars):\n{response[:500]}")
            lines = response.split("\n")

            # Find system status line (header)
            system_line = None
            for line in lines:
                if "Power" in line and "Baud" in line:
                    system_line = line
                    logger.debug(f"Found system status header: {line}")
                    break

            if not system_line:
                logger.error(f"Could not find system status line. Response lines: {lines[:10]}")
                raise ParseError(
                    "Unable to parse device status response. The device response appears to be in an unexpected format. "
                    "Please check the device connection and try again."
                )

            # Parse system status
            # Format: Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
            # The line after the header contains the values
            status_line_idx = None
            for i, line in enumerate(lines):
                if i > 0 and "Power" in lines[i-1] and "Baud" in lines[i-1]:
                    status_line_idx = i
                    break

            if status_line_idx is None or status_line_idx >= len(lines):
                raise ParseError(
                    "Unable to find status data in device response. The device may have returned an incomplete response. "
                    "Please try the command again."
                )

            status_line = lines[status_line_idx]
            parts = status_line.split()

            if len(parts) < 8:
                raise ParseError(
                    f"Device status response is incomplete. Expected 8 fields but found only {len(parts)}. "
                    f"This may indicate a communication issue with the device. Please check the connection and try again."
                )

            power = parts[0] if len(parts) > 0 else "Unknown"
            baud = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 57600
            level_unit = parts[2] if len(parts) > 2 else "%"
            auto_standby = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

            # DSP usage may or may not have % suffix
            dsp_str = parts[4].rstrip("%") if len(parts) > 4 else "0"
            try:
                dsp_usage = float(dsp_str)
            except ValueError:
                logger.warning(f"Could not parse DSP usage '{parts[4]}', using 0.0")
                dsp_usage = 0.0
                # Note: We continue with a default value rather than failing, as this is a non-critical field

            fade = parts[5] == "On" if len(parts) > 5 else False

            # Temperature parsing with error handling
            temp_str = parts[6] if len(parts) > 6 else "0C"
            try:
                temperature = float(temp_str.rstrip("C"))
            except ValueError:
                logger.warning(f"Could not parse temperature '{temp_str}', using 0.0")
                temperature = 0.0
                # Note: We continue with a default value rather than failing, as this is a non-critical field

            uptime = parts[7] if len(parts) > 7 else "0000:00:00:00"

            # Find firmware version
            firmware_version = "Unknown"
            for line in lines:
                if "FW Version:" in line:
                    match = re.search(r"FW Version:([^\n]+)", line)
                    if match:
                        firmware_version = match.group(1).strip()
                    break

            # Parse input settings
            inputs = []
            in_input_section = False
            for line in lines:
                if "Input Settings Status" in line:
                    in_input_section = True
                    continue
                if in_input_section and line.strip().startswith("In"):
                    # Format: In1     On   50  50   Off Off
                    # The Input EQ section that follows uses the same "In<n>"
                    # prefix but encodes per-band data as parts[1]="L[20" /
                    # "R[20", so guard on parts[1] being the Lock value.
                    parts = line.split()
                    if len(parts) >= 6 and parts[1] in ("On", "Off"):
                        port_match = re.match(r"In(\d+)", parts[0])
                        if port_match:
                            port = int(port_match.group(1))
                            lock = parts[1] == "On"
                            gain_l = int(parts[2]) if parts[2].isdigit() else 50
                            gain_r = int(parts[3]) if parts[3].isdigit() else 50
                            # "On" means muted (True), "Off" means not muted (False)
                            mute_l = parts[4] == "On"
                            mute_r = parts[5] == "On"
                            inputs.append(
                                InputSettings(
                                    port=port,
                                    lock=lock,
                                    gain_l=gain_l,
                                    gain_r=gain_r,
                                    mute_l=mute_l,
                                    mute_r=mute_r,
                                )
                            )

            # Parse output routing
            routing = []
            in_routing_section = False
            for line in lines:
                if "Matrix Config Status" in line or "Output" in line and "FromIn" in line:
                    in_routing_section = True
                    continue
                if in_routing_section and line.strip().startswith("Out"):
                    # Format: Out1 L        In1 L   (or "Out1 L  None")
                    # Output Settings rows ("Out1 On 100 100 ...") and Output
                    # EQ rows ("Out1 L[20  ,off ]...") later in the response
                    # also start with "Out<n>"; bound this section by
                    # requiring parts[1] to be a channel literal ("L"/"R").
                    # "L[20" / "On" both fail the literal check.
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] in ("L", "R"):
                        out_match = re.match(r"Out(\d+)", parts[0])
                        if out_match:
                            output = int(out_match.group(1))
                            channel = parts[1]
                            from_input = None
                            # Look for input in remaining parts
                            for part in parts[2:]:
                                if part.startswith("In"):
                                    in_match = re.match(r"In(\d+)", part)
                                    if in_match:
                                        from_input = int(in_match.group(1))
                                        break
                            routing.append(
                                OutputRouting(
                                    output=output,
                                    channel=channel,
                                    from_input=from_input,
                                )
                            )

            return SystemStatus(
                power=power,
                baud=baud,
                level_unit=level_unit,
                auto_standby_time=auto_standby,
                dsp_usage=dsp_usage,
                fade=fade,
                temperature=temperature,
                uptime=uptime,
                firmware_version=firmware_version,
                inputs=inputs,
                routing=routing,
            )
        except ParseError:
            # Re-raise ParseError as-is
            raise
        except (ValueError, IndexError, AttributeError) as e:
            logger.error(f"Failed to parse STATUS response: {e}")
            raise ParseError(
                f"Unable to parse device status response due to a data format error: {str(e)}. "
                "The device may have returned data in an unexpected format. Please check the device connection and try again."
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error parsing STATUS response: {e}")
            raise ParseError(
                f"An unexpected error occurred while parsing the device status response: {str(e)}. "
                "Please check the device connection and try again."
            ) from e

    @staticmethod
    def parse_preset_status(response: str, preset_number: Optional[int] = None) -> PresetStatus:
        """Parse PRESET xx STATUS command response.

        Args:
            response: Raw PRESET STATUS response string
            preset_number: Preset number (if known, will be extracted from response if not provided)

        Returns:
            Parsed PresetStatus object

        Raises:
            ParseError: If parsing fails
        """
        try:
            logger.debug(f"Parsing PRESET STATUS response ({len(response)} chars):\n{response[:500]}")
            lines = response.split("\n")

            # Look for preset information in the response
            # The response format may vary, but typically indicates if preset exists
            # and may contain configuration details
            parsed_preset_number = preset_number
            exists = False
            description = None

            # Try to find preset number from response if not provided
            if parsed_preset_number is None:
                for line in lines:
                    line_lower = line.lower()
                    if "preset" in line_lower:
                        # Try to extract preset number
                        match = re.search(r"preset\s+(\d+)", line_lower)
                        if match:
                            parsed_preset_number = int(match.group(1))
                            break

                # If still not found, try to extract from any numeric value
                if parsed_preset_number is None:
                    for line in lines:
                        match = re.search(r"(\d+)", line)
                        if match:
                            parsed_preset_number = int(match.group(1))
                            if 1 <= parsed_preset_number <= 8:
                                break

            # Parse response content
            for line in lines:
                line_lower = line.lower()

                # Check if preset exists (common indicators)
                if any(indicator in line_lower for indicator in ["exists", "saved", "configured", "active"]):
                    exists = True
                elif any(indicator in line_lower for indicator in ["not found", "empty", "deleted", "none"]):
                    exists = False

                # Try to extract description if present
                if "description" in line_lower or "name" in line_lower:
                    desc_match = re.search(r"(?:description|name)[:\s]+(.+)", line_lower)
                    if desc_match:
                        description = desc_match.group(1).strip()

            if parsed_preset_number is None:
                raise ParseError(
                    "Unable to determine preset number from device response. "
                    "Please ensure you're querying a valid preset (1-8) and try again."
                )

            # If we couldn't determine existence, check if response is empty or error
            if not exists and len(response.strip()) > 0:
                # Non-empty response likely means preset exists
                exists = True

            return PresetStatus(
                preset_number=parsed_preset_number,
                exists=exists,
                description=description,
            )
        except ParseError:
            # Re-raise ParseError as-is
            raise
        except (ValueError, IndexError, AttributeError) as e:
            logger.error(f"Failed to parse PRESET STATUS response: {e}")
            raise ParseError(
                f"Unable to parse preset status response due to a data format error: {str(e)}. "
                "The device may have returned data in an unexpected format. Please check the preset number and try again."
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error parsing PRESET STATUS response: {e}")
            raise ParseError(
                f"An unexpected error occurred while parsing the preset status response: {str(e)}. "
                "Please check the device connection and try again."
            ) from e

    @staticmethod
    def parse_simple_response(response: str) -> str:
        """Parse simple text response (most commands).

        Args:
            response: Raw response string

        Returns:
            Cleaned response text
        """
        # Remove welcome message if present
        lines = response.split("\n")
        cleaned_lines = []
        skip_until_separator = True
        found_separator = False

        for line in lines:
            if "===" in line:
                skip_until_separator = False
                found_separator = True
                continue
            if not skip_until_separator:
                # Skip welcome/banner lines even after separator
                line_stripped = line.strip().lower()
                if (line_stripped and
                    ("welcome" in line_stripped or
                     "dmp168 terminal control system" in line_stripped or
                     "type \"help\" for more information" in line_stripped or
                     "fw version:" in line_stripped)):
                    continue
                cleaned_lines.append(line)

        result = "\n".join(cleaned_lines).strip()

        # If no separator was found, try to extract meaningful content
        # by removing common welcome/banner text
        if not found_separator and not result:
            # Look for non-empty lines that aren't welcome messages
            for line in lines:
                line_stripped = line.strip()
                # Skip empty lines, welcome messages, and command echoes
                if (line_stripped and
                    "welcome" not in line_stripped.lower() and
                    "help" not in line_stripped.lower() and
                    "dmp168" not in line_stripped.lower() and
                    "fw version" not in line_stripped.lower() and
                    not line_stripped.startswith(">") and
                    len(line_stripped) < 100):  # Skip long banner text
                    cleaned_lines.append(line_stripped)
            result = "\n".join(cleaned_lines).strip()

        # If still empty, return the original response stripped (might be a simple value)
        if not result:
            result = response.strip()

        return result

