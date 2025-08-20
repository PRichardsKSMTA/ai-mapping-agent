#!/usr/bin/env python3
"""Streamlit startup script that enables post-processing."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    """Launch the Streamlit app with post-processing enabled."""
    os.environ["ENABLE_POSTPROCESS"] = "1"
    subprocess.run(["streamlit", "run", "app.py", *sys.argv[1:]], check=True)


if __name__ == "__main__":
    main()
