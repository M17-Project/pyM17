"""M17 Audio Processing

This module provides audio processing components for M17:
- Codec2 wrapper for voice encoding/decoding
- Audio processing blocks for building audio pipelines

Note: Audio dependencies (pycodec2, soundcard, samplerate) are optional.
Install with: pip install m17[audio]
"""

from m17.audio.codec2 import (
    HAS_CODEC2,
    Codec2Mode,
    Codec2Wrapper,
)

__all__ = [
    "Codec2Mode",
    "Codec2Wrapper",
    "HAS_CODEC2",
]

# Conditionally export blocks if available
try:
    from m17.audio.blocks import (
        AudioBlock,
        Codec2Decoder,
        Codec2Encoder,
        M17Framer,
        M17Parser,
        MicrophoneSource,
        SpeakerSink,
    )

    __all__.extend(
        [
            "AudioBlock",
            "MicrophoneSource",
            "SpeakerSink",
            "Codec2Encoder",
            "Codec2Decoder",
            "M17Framer",
            "M17Parser",
        ]
    )
except ImportError:
    pass
