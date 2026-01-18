"""
M17 Audio Processing Blocks

Provides building blocks for audio processing pipelines.
These can be connected together to create complete audio paths
for encoding, decoding, and streaming M17 audio.

Note: Requires optional dependencies (soundcard, samplerate).
Install with: pip install m17[audio]
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

import numpy as np

from m17.core.address import Address
from m17.frames.ip import IPFrame
from m17.frames.stream import M17Payload

try:
    import soundcard as sc
    HAS_SOUNDCARD = True
except ImportError:
    HAS_SOUNDCARD = False
    sc = None

try:
    import samplerate
    HAS_SAMPLERATE = True
except ImportError:
    HAS_SAMPLERATE = False
    samplerate = None

from m17.audio.codec2 import Codec2Wrapper, Codec2Mode, HAS_CODEC2

__all__ = [
    "AudioBlock",
    "MicrophoneSource",
    "SpeakerSink",
    "Codec2Encoder",
    "Codec2Decoder",
    "M17Framer",
    "M17Parser",
    "Tee",
    "Null",
]

logger = logging.getLogger(__name__)

T = TypeVar("T")
U = TypeVar("U")


class AudioBlock(ABC, Generic[T, U]):
    """
    Base class for audio processing blocks.

    Blocks can be connected in a chain, with each block
    processing data and passing it to the next.
    """

    def __init__(self) -> None:
        """Initialize block."""
        self._input_queue: queue.Queue[T] = queue.Queue()
        self._output_queue: Optional[queue.Queue[U]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def connect(self, output_queue: queue.Queue[U]) -> None:
        """Connect output to another block's input queue."""
        self._output_queue = output_queue

    def put(self, item: T) -> None:
        """Put an item into this block's input queue."""
        self._input_queue.put(item)

    def _emit(self, item: U) -> None:
        """Emit an item to the output queue."""
        if self._output_queue is not None:
            self._output_queue.put(item)

    def start(self) -> None:
        """Start the processing thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the processing thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                item = self._input_queue.get(timeout=0.1)
                result = self.process(item)
                if result is not None:
                    self._emit(result)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Block processing error: {e}")

    @abstractmethod
    def process(self, item: T) -> Optional[U]:
        """
        Process a single item.

        Args:
            item: Input item.

        Returns:
            Processed output, or None to skip.
        """
        pass


@dataclass
class MicrophoneSource:
    """
    Audio source from system microphone.

    Captures audio at 8kHz mono and emits int16 numpy arrays.
    """

    samples_per_frame: int = 160
    _output_queue: Optional[queue.Queue] = field(default=None, init=False)
    _running: bool = field(default=False, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)

    def connect(self, output_queue: queue.Queue) -> None:
        """Connect to output queue."""
        self._output_queue = output_queue

    def start(self) -> None:
        """Start capturing audio."""
        if not HAS_SOUNDCARD:
            raise ImportError("soundcard not installed")

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _capture_loop(self) -> None:
        """Audio capture loop."""
        mic = sc.default_microphone()
        with mic.recorder(samplerate=8000, channels=1, blocksize=self.samples_per_frame) as recorder:
            while self._running:
                audio = recorder.record(numframes=self.samples_per_frame)
                # Convert float [-1, 1] to int16
                audio = (audio.flatten() * 32767).astype(np.int16)
                if self._output_queue:
                    self._output_queue.put(audio)


@dataclass
class SpeakerSink:
    """
    Audio sink to system speaker.

    Plays int16 numpy arrays at 8kHz mono.
    """

    _input_queue: queue.Queue = field(default_factory=queue.Queue, init=False)
    _running: bool = field(default=False, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)

    def put(self, audio: np.ndarray) -> None:
        """Put audio data to play."""
        self._input_queue.put(audio)

    def start(self) -> None:
        """Start playback."""
        if not HAS_SOUNDCARD:
            raise ImportError("soundcard not installed")

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop playback."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _playback_loop(self) -> None:
        """Audio playback loop."""
        speaker = sc.default_speaker()
        with speaker.player(samplerate=8000, channels=1) as player:
            while self._running:
                try:
                    audio = self._input_queue.get(timeout=0.1)
                    # Convert int16 to float [-1, 1]
                    audio = audio.astype(np.float32) / 32767
                    player.play(audio)
                except queue.Empty:
                    # Play silence if no data
                    player.play(np.zeros(160, dtype=np.float32))


class Codec2Encoder(AudioBlock[np.ndarray, bytes]):
    """
    Encode audio to Codec2 bits.

    Input: int16 numpy arrays (160 samples for 3200bps mode)
    Output: bytes (8 bytes per frame for 3200bps mode)
    """

    def __init__(self, mode: Codec2Mode = Codec2Mode.MODE_3200) -> None:
        """Initialize encoder."""
        super().__init__()
        if not HAS_CODEC2:
            raise ImportError("pycodec2 not installed")
        self._codec = Codec2Wrapper(mode)

    def process(self, audio: np.ndarray) -> Optional[bytes]:
        """Encode audio frame."""
        return self._codec.encode(audio)


class Codec2Decoder(AudioBlock[bytes, np.ndarray]):
    """
    Decode Codec2 bits to audio.

    Input: bytes (8 bytes per frame for 3200bps mode)
    Output: int16 numpy arrays (160 samples for 3200bps mode)
    """

    def __init__(self, mode: Codec2Mode = Codec2Mode.MODE_3200) -> None:
        """Initialize decoder."""
        super().__init__()
        if not HAS_CODEC2:
            raise ImportError("pycodec2 not installed")
        self._codec = Codec2Wrapper(mode)

    def process(self, bits: bytes) -> Optional[np.ndarray]:
        """Decode audio frame."""
        return self._codec.decode(bits)


@dataclass
class M17Framer:
    """
    Frame Codec2 data into M17 IP frames.

    Combines 2 Codec2 frames (16 bytes) into one M17 payload.
    """

    dst: str
    src: str
    stream_type: int = 0x0005
    nonce: bytes = field(default_factory=lambda: bytes(14))

    _stream_id: int = field(default_factory=lambda: random.randint(1, 0xFFFF), init=False)
    _frame_number: int = field(default=0, init=False)
    _buffer: bytearray = field(default_factory=bytearray, init=False)
    _input_queue: queue.Queue = field(default_factory=queue.Queue, init=False)
    _output_queue: Optional[queue.Queue] = field(default=None, init=False)

    def connect(self, output_queue: queue.Queue) -> None:
        """Connect to output queue."""
        self._output_queue = output_queue

    def put(self, codec2_frame: bytes) -> None:
        """Add Codec2 frame data."""
        self._buffer.extend(codec2_frame)

        # Emit M17 frame when we have 16 bytes
        while len(self._buffer) >= 16:
            payload = bytes(self._buffer[:16])
            self._buffer = self._buffer[16:]

            frame = IPFrame.create(
                dst=self.dst,
                src=self.src,
                stream_id=self._stream_id,
                stream_type=self.stream_type,
                nonce=self.nonce,
                frame_number=self._frame_number,
                payload=payload,
            )

            if self._output_queue:
                self._output_queue.put(frame)

            self._frame_number = (self._frame_number + 1) & 0x7FFF

    def end_stream(self) -> None:
        """End the stream with EOT frame."""
        # Pad remaining buffer if needed
        if len(self._buffer) > 0:
            self._buffer.extend(bytes(16 - len(self._buffer)))
            payload = bytes(self._buffer[:16])
        else:
            payload = bytes(16)

        frame = IPFrame.create(
            dst=self.dst,
            src=self.src,
            stream_id=self._stream_id,
            stream_type=self.stream_type,
            nonce=self.nonce,
            frame_number=self._frame_number | 0x8000,  # EOT flag
            payload=payload,
        )

        if self._output_queue:
            self._output_queue.put(frame)

        # Reset for next stream
        self._stream_id = random.randint(1, 0xFFFF)
        self._frame_number = 0
        self._buffer.clear()


class M17Parser(AudioBlock[IPFrame, bytes]):
    """
    Parse M17 IP frames and extract Codec2 payload.

    Input: IPFrame
    Output: bytes (16-byte payload, typically 2 Codec2 frames)
    """

    def process(self, frame: IPFrame) -> Optional[bytes]:
        """Extract payload from frame."""
        return frame.payload.payload


class Tee(AudioBlock[T, T]):
    """
    Pass-through block that prints items.

    Useful for debugging pipelines.
    """

    def __init__(self, label: str = "") -> None:
        """Initialize with optional label."""
        super().__init__()
        self.label = label

    def process(self, item: T) -> T:
        """Print and pass through."""
        if isinstance(item, bytes):
            print(f"{self.label}: {item.hex()}")
        else:
            print(f"{self.label}: {item}")
        return item


class Null(AudioBlock[T, None]):
    """
    Sink that discards all input.

    Useful for terminating pipelines.
    """

    def process(self, item: T) -> None:
        """Discard item."""
        return None
