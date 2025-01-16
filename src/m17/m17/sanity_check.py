import sys
import time

if __name__ == "__main__":
    try:
        import soundcard as sc
        import pycodec2
        import numpy
        print("Successfully imported pycodec2 and soundcard modules, everything should work.")
        sys.exit(0)
    except Exception as e:
        print(e)
        print("Could not import pycodec2 and soundcard modules, you may want to install extra features by doing `pip install m17[Codec2]` later.`")
        sys.exit(1)
        
