"""Test configuration — registers adapters before collection."""

from averspec import define_config

# Import adapters (side-effect: registers handlers)
from tests.spike_adapters.task_board_unit import adapter as unit_adapter
from tests.spike_adapters.task_board_async import adapter as async_adapter

# Validate completeness and register
define_config(adapters=[unit_adapter, async_adapter])
