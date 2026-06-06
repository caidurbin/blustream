#!/usr/bin/env python3
"""Vary input gain using a linear triangular wave and restore original gain."""

import asyncio
import sys
import time
from typing import Optional

from blustream import DMP168
from blustream.base.exceptions import BlustreamError, ConnectionError


async def vary_volume_sine(
    host: str,
    input_ch: int,
    duration: float,
    stored_gain: Optional[int] = None,
    port: int = 23,
    timeout: float = 5.0,
) -> None:
    """Vary input gain from 50% using a linear triangular wave and restore original gain.

    This function ONLY affects the specified input channel. It does not modify
    any output channels or other inputs.

    The gain will vary linearly: 50% -> 75% -> 25% -> 50%
    in 100 steps over the specified duration, then restore to the stored gain.

    Args:
        host: Device hostname or IP address
        input_ch: Input channel (1-16, or 0=All). Required.
        duration: Duration of the variation in seconds. Required.
        stored_gain: Original gain to restore at end (0-100). If None,
                     will be read from device status.
        port: TCP port (default 23)
        timeout: Connection timeout in seconds
    """
    device = DMP168(host=host, port=port, timeout=timeout)

    try:
        # Connect to device
        print(f"Connecting to {host}:{port}...")
        await device.connect()
        print("Connected.")

        # Get current gain from status if not provided
        if stored_gain is None:
            print("Reading current input gain from device status...")
            status = await device.get_status()
            # Find the input in the status
            input_settings = next(
                (inp for inp in status.inputs if inp.port == input_ch), None
            )
            if input_settings:
                # Use average of L and R channels, or just L if they differ
                stored_gain = (input_settings.gain_l + input_settings.gain_r) // 2
                print(
                    f"Found current gain: L={input_settings.gain_l}%, R={input_settings.gain_r}%"
                )
                print(f"Using average: {stored_gain}% as stored gain.")
            else:
                stored_gain = 50
                print(
                    f"Input {input_ch} not found in status. Using {stored_gain}% as stored gain."
                )

        print(f"Operating on INPUT {input_ch} only (outputs will not be affected)")
        print(f"Stored gain: {stored_gain}% (will be restored at end)")
        print("Starting from 50% and varying with linear triangular wave...")

        # Calculate linear triangular wave parameters
        # Pattern: midpoint (50%) -> max (75%) -> min (25%) -> midpoint (50%)
        center = 50  # Center/midpoint of wave
        amplitude = 25  # Amplitude of variation (±25%)
        min_gain = center - amplitude  # 25%
        max_gain = center + amplitude  # 75%
        num_steps = 100

        print(
            f"\nVarying gain linearly: {center}% -> {max_gain}% -> {min_gain}% -> {center}%"
        )

        # Measure command execution time to determine feasible step count
        print("Measuring command execution time...")
        test_start = time.time()
        await device.set_input_gain(input_ch=input_ch, gain=center, unit="percent")
        command_time = time.time() - test_start

        # Calculate maximum feasible steps based on command execution time
        # Reserve 10% of duration for overhead
        available_time = duration * 0.9
        max_feasible_steps = (
            int(available_time / command_time) if command_time > 0 else num_steps
        )

        if max_feasible_steps < num_steps:
            print(
                f"Warning: Command execution time ({command_time:.3f}s) is too slow for {num_steps} steps."
            )
            print(
                f"Reducing to {max_feasible_steps} steps to complete within {duration}s duration."
            )
            num_steps = max(1, max_feasible_steps)  # At least 1 step

        print(f"Using triangular wave over {duration} seconds ({num_steps} steps)...")
        print("Starting variation...\n")

        # Vary gain using linear triangular wave
        # Use timer-based approach to ensure exact duration
        start_time = time.time()

        for step in range(num_steps + 1):
            # Calculate progress from 0 to 1
            t = step / num_steps

            # Calculate linear triangular wave value
            # Phase 1 (0.0 to 0.25): midpoint to max (50% to 75%)
            if t <= 0.25:
                # Interpolate from 50% to 75%
                local_t = t / 0.25  # 0 to 1 within this phase
                volume = center + amplitude * local_t
            # Phase 2 (0.25 to 0.75): max to min (75% to 25%)
            elif t <= 0.75:
                # Interpolate from 75% to 25%
                local_t = (t - 0.25) / 0.5  # 0 to 1 within this phase
                volume = max_gain - (max_gain - min_gain) * local_t
            # Phase 3 (0.75 to 1.0): min to midpoint (25% to 50%)
            else:
                # Interpolate from 25% to 50%
                local_t = (t - 0.75) / 0.25  # 0 to 1 within this phase
                volume = min_gain + (center - min_gain) * local_t

            # Round to nearest integer
            volume_int = round(volume)

            # Clamp to valid range (0-100)
            volume_int = max(0, min(100, volume_int))

            # Set input gain (only affects the specified input, not outputs)
            await device.set_input_gain(
                input_ch=input_ch, gain=volume_int, unit="percent"
            )

            # Progress indicator
            if (
                step % max(1, num_steps // 10) == 0
            ):  # Adjust progress reporting for fewer steps
                elapsed = time.time() - start_time
                print(
                    f"Step {step:3d}/{num_steps}: Gain = {volume_int:3d}% (t={t:.3f}, elapsed={elapsed:.2f}s)"
                )

            # Sleep until target time for next step (except on last step)
            if step < num_steps:
                current_time = time.time()
                # Target time for next step
                next_target_time = start_time + ((step + 1) / num_steps) * duration
                sleep_time = next_target_time - current_time
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                # If we're behind schedule, continue anyway (don't skip steps)

        print(f"\nRestoring gain to {stored_gain}%...")
        await device.set_input_gain(input_ch=input_ch, gain=stored_gain, unit="percent")
        print("Gain restored.")

    except ConnectionError as e:
        print(f"Error: Failed to connect to {host}:{port}: {e}", file=sys.stderr)
        sys.exit(1)
    except BlustreamError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted. Restoring gain...")
        try:
            await device.set_input_gain(
                input_ch=input_ch, gain=stored_gain, unit="percent"
            )
            print("Gain restored.")
        except:
            pass
        sys.exit(1)
    finally:
        await device.disconnect()
        print("Disconnected.")


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: vary_volume.py <host> <input> <duration> [stored_gain]")
        print("  host: Device IP address or hostname (required)")
        print("  input: Input channel number (1-16, or 0=All) (required)")
        print("  duration: Duration of variation in seconds (required)")
        print("  stored_gain: Original gain to restore (0-100)")
        print("             Note: If not provided, will be read from device status")
        print("\nNote: This script ONLY affects the specified input channel.")
        print("      Output channels are not modified.")
        print("\nExample:")
        print("  python3 vary_volume.py 192.0.2.100 1 10")
        return 1

    host = sys.argv[1]
    try:
        input_ch = int(sys.argv[2])
    except (ValueError, IndexError):
        print(
            "Error: Input channel number is required and must be an integer",
            file=sys.stderr,
        )
        return 1

    try:
        duration = float(sys.argv[3])
    except (ValueError, IndexError):
        print("Error: Duration is required and must be a number", file=sys.stderr)
        return 1

    stored_gain = int(sys.argv[4]) if len(sys.argv) > 4 else None

    if input_ch < 0 or input_ch > 16:
        print("Error: Input must be 0-16 (0=All)", file=sys.stderr)
        return 1

    if duration <= 0:
        print("Error: Duration must be greater than 0", file=sys.stderr)
        return 1

    if stored_gain is not None and (stored_gain < 0 or stored_gain > 100):
        print("Error: Stored gain must be 0-100", file=sys.stderr)
        return 1

    try:
        asyncio.run(
            vary_volume_sine(
                host=host, input_ch=input_ch, duration=duration, stored_gain=stored_gain
            )
        )
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
