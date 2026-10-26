"""
Test JWT secret key security enforcement
-----------------------------------------
Asserts that the application strictly refuses to initialize or run
if JWT_SECRET_KEY is missing, empty, or shorter than 32 characters.
Tested via isolated Python processes to guarantee true startup verification.
"""
import os
import sys
import subprocess
import pytest

PYTHON_EXE = sys.executable

def test_jwt_secret_enforcement_missing():
    """If JWT_SECRET_KEY is unset or empty, auth module must raise RuntimeError on import."""
    env = {k: v for k, v in os.environ.items() if k != "JWT_SECRET_KEY"}
    env["PYTHONPATH"] = "backend"
    
    cmd = [PYTHON_EXE, "-c", "import app.auth"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    assert res.returncode != 0
    assert "FATAL: JWT_SECRET_KEY must be set in the environment" in res.stderr

def test_jwt_secret_enforcement_too_short():
    """If JWT_SECRET_KEY is < 32 characters, auth module must raise RuntimeError on import."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    env["JWT_SECRET_KEY"] = "short_key_under_32_chars"
    
    cmd = [PYTHON_EXE, "-c", "import app.auth"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    assert res.returncode != 0
    assert "at least 32 characters long" in res.stderr

def test_jwt_secret_enforcement_valid():
    """If JWT_SECRET_KEY is >= 32 characters, auth module imports cleanly."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    env["JWT_SECRET_KEY"] = "a_very_secure_jwt_secret_key_that_exceeds_32_characters_long!"
    
    cmd = [PYTHON_EXE, "-c", "import app.auth as a; assert len(a.JWT_SECRET_KEY) >= 32; print('LOADED_OK')"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    assert "LOADED_OK" in res.stdout
