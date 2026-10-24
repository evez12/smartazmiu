"""Print the OpenAPI document; the web client types are generated from it (``make openapi``)."""

import json
import sys

from app.main import create_app


def main() -> None:
    schema = create_app().openapi()
    document = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    # Bytes, so the output is UTF-8 regardless of the console code page (cp1252 on Windows).
    sys.stdout.buffer.write(document.encode("utf-8"))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
