import os
import subprocess
from pathlib import Path


def test_setup_creates_runtime_before_migrations(tmp_path):
    root = Path(__file__).resolve().parents[3]
    (tmp_path / "Makefile").write_text((root / "Makefile").read_text())
    (tmp_path / "frontend").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # All dependency commands are stubbed; the migration still opens a real DB.
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/usr/bin/env python3\nimport sqlite3, sys\n"
        "if 'alembic' in sys.argv:\n"
        "    sqlite3.connect('runtime/setup-test.db').close()\n"
    )
    uv.chmod(0o755)
    npm = bin_dir / "npm"
    npm.write_text("#!/bin/sh\nexit 0\n")
    npm.chmod(0o755)
    result = subprocess.run(
        ["make", "setup"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "runtime/setup-test.db").is_file()
