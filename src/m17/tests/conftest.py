"""Pytest configuration and fixtures for pyM17 tests.

This module provides shared fixtures and configuration for the test suite.
"""

import random

import pytest

# Fixed seed for reproducible tests
# This ensures example_bytes() and other random data generates
# the same values across test runs
RANDOM_SEED = 42


@pytest.fixture(autouse=True)
def seed_random():
    """Seed the random number generator for reproducible tests.

    This fixture runs automatically before each test to ensure
    deterministic behavior from random.getrandbits() and other
    random functions used by example_bytes() and similar utilities.
    """
    random.seed(RANDOM_SEED)
    yield
    # No cleanup needed - each test gets a fresh seed
