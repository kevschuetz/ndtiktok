"""Fixtures for tests/scan (plan 01-06 additions)."""

import os

import pytest

from ndc.db import Database


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])
