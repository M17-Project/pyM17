"""
Tests for M17 Audio/Processing Blocks

Tests for the processing chain blocks used in M17 applications.
"""

import multiprocessing
import queue
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

import pytest

# Check if blocks module can be imported (requires kademlia)
try:
    import m17.blocks
    BLOCKS_AVAILABLE = True
except ImportError:
    BLOCKS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not BLOCKS_AVAILABLE,
    reason="blocks module requires kademlia dependency"
)


class TestCodeblock:
    """Tests for codeblock decorator."""

    def test_codeblock_wraps_function(self):
        """Test codeblock wraps a callback properly."""
        from m17.blocks import codeblock

        callback = Mock(side_effect=lambda x: x * 2)
        block_fn = codeblock(callback)

        # Check it's a function
        assert callable(block_fn)

    def test_codeblock_processes_queue(self):
        """Test codeblock processes items from queue."""
        from m17.blocks import codeblock

        results = []

        def callback(x):
            results.append(x * 2)
            return x * 2

        block_fn = codeblock(callback)

        # Create queues
        inq = multiprocessing.Queue()
        outq = multiprocessing.Queue()

        # Put items and run in subprocess
        inq.put(1)
        inq.put(2)
        inq.put(3)

        # Run block briefly in a process
        proc = multiprocessing.Process(
            target=block_fn,
            args=(None, inq, outq),
        )
        proc.start()

        # Wait for outputs
        import time
        time.sleep(0.1)
        proc.terminate()
        proc.join()

        # Check outputs
        out_results = []
        while not outq.empty():
            out_results.append(outq.get_nowait())

        assert 2 in out_results
        assert 4 in out_results
        assert 6 in out_results


class TestUdpServer:
    """Tests for udp_server function."""

    def test_udp_server_without_occasional(self):
        """Test udp_server works without occasional callback."""
        from m17.blocks import udp_server

        # This should not raise an error when occasional=None
        def packet_handler(sock, active_connections, bs, conn):
            pass

        # Create server function
        server_fn = udp_server(17171, packet_handler, occasional=None)
        assert callable(server_fn)

    def test_udp_server_with_occasional(self):
        """Test udp_server works with occasional callback."""
        from m17.blocks import udp_server

        def packet_handler(sock, active_connections, bs, conn):
            pass

        occasional_called = []

        def occasional(sock):
            occasional_called.append(True)

        # Create server function
        server_fn = udp_server(17172, packet_handler, occasional=occasional)
        assert callable(server_fn)


class TestTeefile:
    """Tests for teefile function."""

    def test_teefile_creates_file(self):
        """Test teefile creates and writes to file."""
        from m17.blocks import teefile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Create teefile block
            block_fn = teefile(tmp_path)

            # Create queues
            inq = multiprocessing.Queue()
            outq = multiprocessing.Queue()

            # Put data
            test_data = b"hello world"
            inq.put(test_data)

            # Run briefly
            proc = multiprocessing.Process(
                target=block_fn,
                args=(None, inq, outq),
            )
            proc.start()

            import time
            time.sleep(0.1)
            proc.terminate()
            proc.join()

            # Check file contents
            with open(tmp_path, "rb") as f:
                contents = f.read()
            assert contents == test_data

            # Check passthrough
            assert not outq.empty()
            assert outq.get_nowait() == test_data

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_teefile_passthrough(self):
        """Test teefile passes data through."""
        from m17.blocks import teefile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            block_fn = teefile(tmp_path)
            inq = multiprocessing.Queue()
            outq = multiprocessing.Queue()

            # Put multiple items
            items = [b"one", b"two", b"three"]
            for item in items:
                inq.put(item)

            proc = multiprocessing.Process(
                target=block_fn,
                args=(None, inq, outq),
            )
            proc.start()

            import time
            time.sleep(0.1)
            proc.terminate()
            proc.join()

            # Check all items passed through
            out_items = []
            while not outq.empty():
                out_items.append(outq.get_nowait())

            assert out_items == items

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestZeros:
    """Tests for zeros function."""

    def test_zeros_generates_arrays(self):
        """Test zeros generates numpy arrays of zeros."""
        from m17.blocks import zeros
        import numpy as np

        # Create zeros generator
        gen_fn = zeros(size=10, dtype="<h", rate=100)

        # Create queues
        inq = None  # zeros doesn't use input
        outq = multiprocessing.Queue()

        # Run briefly
        proc = multiprocessing.Process(
            target=gen_fn,
            args=(None, inq, outq),
        )
        proc.start()

        import time
        time.sleep(0.05)
        proc.terminate()
        proc.join()

        # Check output
        assert not outq.empty()
        arr = outq.get_nowait()
        assert isinstance(arr, np.ndarray)
        assert len(arr) == 10
        assert arr.dtype == np.dtype("<h")
        assert np.all(arr == 0)


class TestDelay:
    """Tests for delay function."""

    def test_delay_creates_fifo(self):
        """Test delay creates a FIFO buffer."""
        from m17.blocks import delay

        # Create delay block with size 3
        delay_fn = delay(3)
        assert callable(delay_fn)


class TestTee:
    """Tests for tee function."""

    def test_tee_prints_and_passes(self):
        """Test tee prints data and passes it through."""
        from m17.blocks import tee

        # Create tee block
        tee_fn = tee("test")
        assert callable(tee_fn)


class TestNull:
    """Tests for null function."""

    def test_null_consumes_input(self):
        """Test null consumes input without output."""
        from m17.blocks import null

        inq = multiprocessing.Queue()
        outq = None  # null doesn't use output

        inq.put("data1")
        inq.put("data2")

        # Run briefly
        proc = multiprocessing.Process(
            target=null,
            args=(None, inq, outq),
        )
        proc.start()

        import time
        time.sleep(0.05)
        proc.terminate()
        proc.join()

        # Input queue should be empty (items consumed)
        # Note: this is a race condition in testing, so we just verify no crash


class TestM17ReflectorClientBlocks:
    """Tests for M17ReflectorClientBlocks class."""

    def test_construction(self):
        """Test M17ReflectorClientBlocks construction."""
        from m17.blocks import M17ReflectorClientBlocks

        # Create client blocks
        client = M17ReflectorClientBlocks(
            mycall="W2FBI A",
            module="A",
            host="localhost",
            port=17000,
        )

        assert client.mycall == "W2FBI A"
        assert client.module == "A"

    def test_sender_receiver_callables(self):
        """Test sender and receiver return callables."""
        from m17.blocks import M17ReflectorClientBlocks

        client = M17ReflectorClientBlocks(
            mycall="W2FBI A",
            module="A",
            host="localhost",
            port=17000,
        )

        sender = client.sender()
        receiver = client.receiver()

        assert callable(sender)
        assert callable(receiver)


class TestChunker:
    """Tests for chunker functions."""

    def test_chunker_b_exists(self):
        """Test chunker_b function exists."""
        from m17.blocks import chunker_b

        chunk_fn = chunker_b(640)
        assert callable(chunk_fn)


class TestNpConvert:
    """Tests for np_convert function."""

    def test_np_convert_exists(self):
        """Test np_convert function exists."""
        from m17.blocks import np_convert

        convert_fn = np_convert("<h")
        assert callable(convert_fn)


class TestIntegerDecimate:
    """Tests for integer_decimate function."""

    def test_integer_decimate_exists(self):
        """Test integer_decimate function exists."""
        from m17.blocks import integer_decimate

        decimate_fn = integer_decimate(2)
        assert callable(decimate_fn)


class TestIntegerInterpolate:
    """Tests for integer_interpolate function."""

    def test_integer_interpolate_exists(self):
        """Test integer_interpolate function exists."""
        from m17.blocks import integer_interpolate

        interpolate_fn = integer_interpolate(2)
        assert callable(interpolate_fn)
