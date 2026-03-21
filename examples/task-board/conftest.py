"""Register both adapters for the task board example."""

from averspec import define_config

from adapters.task_board_unit import adapter as unit_adapter
from adapters.task_board_http import adapter as http_adapter

define_config(adapters=[unit_adapter, http_adapter])
