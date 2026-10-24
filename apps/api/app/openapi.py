"""Print the OpenAPI document; the web client types are generated from it (``make openapi``)."""

import json
import sys

from app.main import create_app


def main() -> None:
    schema = create_app().openapi()
    sys.stdout.write(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
