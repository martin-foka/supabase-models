"""
Command-line interface for supabase-models.

Entry point for running supabase-models as a module.
"""

import argparse
import logging
import sys
from importlib.metadata import version
from typing import NoReturn

from supabase_models.config import DEFAULT_OUTPUT_FILE
from supabase_models.config import DEFAULT_SCHEMA
from supabase_models.generator import ModelGenerator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", stream=sys.stderr)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="supabase-models",
        description="Generate Pydantic models from Supabase database schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable
  export DATABASE_URL="postgresql://user:password@localhost:5432/database"
  supabase-models

  # Using command line argument
  supabase-models --database-url postgresql://user:password@localhost:5432/database

  # Custom output and schema
  supabase-models --output my_models.py --schema public --verbose

  # Using custom template
  supabase-models --template my_custom_template.jinja2
        """,
    )

    parser.add_argument("--database-url", help="PostgreSQL database URL (overrides DATABASE_URL env var)")

    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file for generated models (default: {DEFAULT_OUTPUT_FILE})",
    )

    parser.add_argument(
        "-s",
        "--schema",
        default=DEFAULT_SCHEMA,
        help=f"Database schema to introspect (default: {DEFAULT_SCHEMA})",
    )

    parser.add_argument("-t", "--template", help="Custom template file path (default: built-in template.jinja2)")

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument("--version", action="version", version=f"supabase-models {version('supabase-models')}")

    return parser


def handle_error(error: BaseException, error_type: str) -> NoReturn:
    """Handle and format CLI errors."""
    logger = logging.getLogger(__name__)

    if error_type == "config":
        logger.error(f"Configuration error: {error}")
        logger.error("Quick fix:")
        logger.error("   Set DATABASE_URL: export DATABASE_URL='postgresql://user:pass@host:port/db'")
        logger.error("   Or use: supabase-models --database-url 'postgresql://...'")
    elif error_type == "keyboard":
        logger.error("Operation cancelled by user")
    else:
        logger.error(f"Unexpected error: {error}")
        logger.error("Try running with --verbose for more details")

    sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        generator = ModelGenerator(
            database_url=args.database_url,
            output_filename=args.output,
            template_name=args.template,
            schema=args.schema,
        )
        generator.run()

    except ValueError as e:
        handle_error(e, "config")
    except KeyboardInterrupt as e:
        handle_error(e, "keyboard")
    except Exception as e:
        handle_error(e, "unexpected")


if __name__ == "__main__":
    main()
