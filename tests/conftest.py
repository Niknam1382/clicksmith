"""Test bootstrap: keep every test away from the real user data folder."""

import atexit
import os
import shutil
import tempfile

_HOME = tempfile.mkdtemp(prefix="clicksmith-tests-")
os.environ["CLICKSMITH_HOME"] = _HOME
atexit.register(shutil.rmtree, _HOME, ignore_errors=True)
