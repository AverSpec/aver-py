"""Dogfood test configuration."""

from averspec import define_config
from tests.acceptance.adapter import adapter as acceptance_adapter

define_config(adapters=[acceptance_adapter])
