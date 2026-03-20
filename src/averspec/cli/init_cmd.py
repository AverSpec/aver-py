"""aver init — interactive scaffolding for new domains."""

import re
import sys

from averspec.cli.scaffold import scaffold_domain


def _to_snake_case(name: str) -> str:
    """Convert a name to snake_case."""
    # Replace hyphens and spaces with underscores
    name = re.sub(r"[-\s]+", "_", name.strip())
    # Insert underscores before uppercase letters (camelCase -> camel_case)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def _to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase for class names."""
    return "".join(part.capitalize() for part in snake.split("_"))


VALID_PROTOCOLS = ("unit", "http", "playwright")


def execute_init() -> None:
    """Run interactive init prompts and scaffold files."""
    print("aver init — scaffold a new domain\n")

    # Domain name
    raw_name = input("Domain name: ").strip()
    if not raw_name:
        print("Error: domain name is required.")
        sys.exit(1)

    snake_name = _to_snake_case(raw_name)
    class_name = _to_class_name(snake_name)

    # Protocol
    print(f"\nProtocol options: {', '.join(VALID_PROTOCOLS)}")
    protocol = input("Protocol [unit]: ").strip().lower() or "unit"

    if protocol not in VALID_PROTOCOLS:
        print(f"Error: unknown protocol '{protocol}'. Choose from: {', '.join(VALID_PROTOCOLS)}")
        sys.exit(1)

    print(f"\nScaffolding '{raw_name}' with {protocol} protocol...\n")

    created = scaffold_domain(
        snake_name=snake_name,
        class_name=class_name,
        domain_label=raw_name,
        protocol=protocol,
    )

    for path in created:
        print(f"  created {path}")

    print("\nDone.")
