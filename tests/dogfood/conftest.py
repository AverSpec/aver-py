"""Dogfood test configuration."""

from averspec import define_config
from tests.dogfood.adapter import adapter as dogfood_adapter

define_config(adapters=[dogfood_adapter])
