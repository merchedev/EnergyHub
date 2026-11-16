from __future__ import annotations

import os
import tempfile

os.environ["ENERGYHUB_DATA_DIR"] = tempfile.mkdtemp(prefix="energyhub-tests-")
os.environ["ENERGYHUB_DEMO"] = "0"
os.environ.pop("HA_URL", None)
os.environ.pop("HA_TOKEN", None)
