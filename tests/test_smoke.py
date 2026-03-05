"""
Smoke tests for Clyro.
"""
import pytest

def test_imports():
    """Verify that core modules can be imported without error."""
    try:
        import clyro.main
        import clyro.app
        import clyro.config
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")

def test_config_defaults():
    """Verify config falls back to sensible defaults without a file."""
    try:
        from clyro.config.schema import Settings
        settings = Settings()
        assert settings is not None
    except Exception as e:
        pytest.fail(f"Failed to load settings: {e}")
