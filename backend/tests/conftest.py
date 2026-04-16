"""
tests/conftest.py — pytest configuration.

CRITICAL: Adds the backend/ directory to sys.path so all imports resolve
correctly when running `pytest` from the backend/ directory.
"""
import sys
import os

# Insert the backend root so `from config import ...` works in tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set a dummy ANTHROPIC_API_KEY so config.py doesn't raise during collection
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-for-pytest")
os.environ.setdefault("TAVILY_API_KEY", "")
os.environ.setdefault("SERPAPI_KEY", "")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test_askweb")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("REFLECTION_ENABLED", "false")  # skip reflection in tests
