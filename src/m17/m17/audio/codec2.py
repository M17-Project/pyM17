"""
M17 Codec2 Wrapper

Provides a type-safe wrapper around pycodec2 for M17 voice encoding.

Codec2 Modes used in M17:
- 3200 bps: 64-bit frames (8 bytes) per 20ms of audio
- 1600 bps: 64-bit frames (8 bytes) per 40ms of audio (half rate)

The standard M17 voice mode uses 3200 bps, producing 8 bytes per
160 samples of 8kHz audio (20ms).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union

import numpy as np

try:
    import pycodec2
    HAS_CODEC2 = True
except ImportError:
    HAS_CODEC2 = False
    pycodec2 = None

__all__ = [
    "Codec2Mode",
    "Codec2Wrapper",
    "HAS_CODEC2",
]


class Codec2Mode(IntEnum):
    """Codec2 operating modes."""

    MODE_3200 = 0  # 3200 bps - M17 standard voice
    MODE_2400 = 1  # 2400 bps
    MODE_1600 = 2  # 1600 bps - M17 half-rate voice
    MODE_1400 = 3  # 1400 bps
    MODE_1300 = 4  # 1300 bps
    MODE_1200 = 5  # 1200 bps
    MODE_700C = 6  # 700C bps
    MODE_450 = 7   # 450 bps
    MODE_450PWB = 8  # 450 bps wideband


# Mapping of mode to bits per frame
MODE_BITS_PER_FRAME = {
    Codec2Mode.MODE_3200: 64,
    Codec2Mode.MODE_2400: 48,
    Codec2Mode.MODE_1600: 64,
    Codec2Mode.MODE_1400: 56,
    Codec2Mode.MODE_1300: 52,
    Codec2Mode.MODE_1200: 48,
    Codec2Mode.MODE_700C: 28,
    Codec2Mode.MODE_450: 18,
    Codec2Mode.MODE_450PWB: 18,
}

# Mapping of mode to samples per frame
MODE_SAMPLES_PER_FRAME = {
    Codec2Mode.MODE_3200: 160,
    Codec2Mode.MODE_2400: 160,
    Codec2Mode.MODE_1600: 320,
    Codec2Mode.MODE_1400: 320,
    Codec2Mode.MODE_1300: 320,
    Codec2Mode.MODE_1200: 320,
    Codec2Mode.MODE_700C: 320,
    Codec2Mode.MODE_450: 320,
    Codec2Mode.MODE_450PWB: 320,
}


@dataclass
class Codec2Wrapper:
    """
    Wrapper for Codec2 voice codec.

    Provides encoding and decoding of voice audio using Codec2.

    Example:
        codec = Codec2Wrapper(Codec2Mode.MODE_3200)

        # Encode audio to bits
        audio = np.zeros(160, dtype=np.int16)  # 20ms of silence
        bits = codec.encode(audio)

        # Decode bits to audio
        audio_out = codec.decode(bits)
    """

    mode: Codec2Mode = Codec2Mode.MODE_3200
    _codec: Optional[object] = None

    def __post_init__(self) -> None:
        """Initialize Codec2 instance."""
        if not HAS_CODEC2:
            raise ImportError(
                "pycodec2 not installed. Install with: pip install pycodec2"
            )
        self._codec = pycodec2.Codec2(int(self.mode))

    @property
    def bits_per_frame(self) -> int:
        """Get bits per frame for current mode."""
        return MODE_BITS_PER_FRAME[self.mode]

    @property
    def bytes_per_frame(self) -> int:
        """Get bytes per frame for current mode."""
        return (self.bits_per_frame + 7) // 8

    @property
    def samples_per_frame(self) -> int:
        """Get audio samples per frame for current mode."""
        return MODE_SAMPLES_PER_FRAME[self.mode]

    @property
    def sample_rate(self) -> int:
        """Get audio sample rate (always 8000 Hz for Codec2)."""
        return 8000

    @property
    def frame_duration_ms(self) -> float:
        """Get frame duration in milliseconds."""
        return self.samples_per_frame / self.sample_rate * 1000

    def encode(self, audio: np.ndarray) -> bytes:
        """
        Encode audio samples to Codec2 bits.

        Args:
            audio: Audio samples as int16 array.
                   Must be exactly samples_per_frame samples.

        Returns:
            Encoded bits as bytes.

        Raises:
            ValueError: If audio length is wrong.
        """
        if len(audio) != self.samples_per_frame:
            raise ValueError(
                f"Audio must be {self.samples_per_frame} samples, got {len(audio)}"
            )

        # Ensure correct dtype
        if audio.dtype != np.int16:
            audio = audio.astype(np.int16)

        return self._codec.encode(audio)

    def decode(self, bits: bytes) -> np.ndarray:
        """
        Decode Codec2 bits to audio samples.

        Args:
            bits: Encoded bits as bytes.
                  Must be exactly bytes_per_frame bytes.

        Returns:
            Decoded audio samples as int16 array.

        Raises:
            ValueError: If bits length is wrong.
        """
        if len(bits) != self.bytes_per_frame:
            raise ValueError(
                f"Bits must be {self.bytes_per_frame} bytes, got {len(bits)}"
            )

        return self._codec.decode(bits)

    def encode_stream(self, audio: np.ndarray) -> list[bytes]:
        """
        Encode a longer audio stream to multiple frames.

        Args:
            audio: Audio samples (any length).

        Returns:
            List of encoded frame bytes.
        """
        frames = []
        samples_per_frame = self.samples_per_frame

        for i in range(0, len(audio), samples_per_frame):
            chunk = audio[i:i + samples_per_frame]
            if len(chunk) < samples_per_frame:
                # Pad last chunk with zeros
                chunk = np.concatenate([
                    chunk,
                    np.zeros(samples_per_frame - len(chunk), dtype=np.int16)
                ])
            frames.append(self.encode(chunk))

        return frames

    def decode_stream(self, frames: list[bytes]) -> np.ndarray:
        """
        Decode multiple frames to audio stream.

        Args:
            frames: List of encoded frame bytes.

        Returns:
            Decoded audio samples.
        """
        audio_chunks = [self.decode(frame) for frame in frames]
        return np.concatenate(audio_chunks) if audio_chunks else np.array([], dtype=np.int16)


def create_codec2(mode: Union[Codec2Mode, int] = Codec2Mode.MODE_3200) -> Codec2Wrapper:
    """
    Create a Codec2 wrapper.

    Args:
        mode: Codec2 mode (default: 3200 bps).

    Returns:
        Configured Codec2Wrapper.
    """
    if isinstance(mode, int) and mode not in [m.value for m in Codec2Mode]:
        mode = Codec2Mode(mode)
    return Codec2Wrapper(mode=Codec2Mode(mode))
