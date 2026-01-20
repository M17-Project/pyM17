"""Provides a test of the soundcard library. It will record from the default microphone and
play back to the default speaker.
"""
from __future__ import annotations

import sys
from typing import NoReturn, Union

import soundcard as sc

try:
    import pycodec2
except Exception as exc:
    raise ImportError("pycodec2 is required for this test.") from exc


def audio_test_soundcard(mode: Union[int, str]) -> NoReturn:
    """Test the soundcard library."""
    mode_int = int(mode)
    c2 = pycodec2.Codec2(mode_int)
    conrate: int = c2.samples_per_frame()
    bitframe: int = c2.bits_per_frame()
    pa_rate = 8000

    default_mic = sc.default_microphone()
    default_speaker = sc.default_speaker()
    print(default_mic, default_speaker)
    sc_config = {"samplerate": pa_rate, "blocksize": conrate}
    with default_mic.recorder(**sc_config, channels=1) as mic, default_speaker.player(
        **sc_config, channels=1
    ) as sp:
        while True:
            audio = mic.record(numframes=conrate)  # .transpose()
            audio = audio.flatten()
            audio = audio * 32767
            audio = audio.astype("<h")
            c2_bits = c2.encode(audio)
            audio = c2.decode(c2_bits)
            audio = audio.astype("float")
            audio = audio / 32767
            sp.play(audio)


if __name__ == "__main__":
    audio_test_soundcard(int(sys.argv[1]))
