"""Allow `python3 -m app` to invoke the CLI."""
from app.cli import main
import sys

sys.exit(main())
