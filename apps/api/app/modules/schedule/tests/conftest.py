# The import fixtures of the academic registry load campus and timetable files too.
from app.modules.academics.tests.conftest import seed, staff_headers, upload

__all__ = ["seed", "staff_headers", "upload"]
