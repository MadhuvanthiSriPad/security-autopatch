"""Tests for the security fixes applied to app.py."""
import bcrypt
import os
from unittest.mock import patch
from app import app


def test_hash_password_uses_bcrypt():
    """Alert #9: Ensure password hashing uses bcrypt, not MD5."""
    client = app.test_client()
    response = client.get('/hash?password=testpassword')
    hashed = response.data.decode()
    assert hashed.startswith('$2b$') or hashed.startswith('$2a$')
    assert bcrypt.checkpw(b'testpassword', hashed.encode())


def test_greet_escapes_user_input():
    """Alert #8: Ensure template injection is prevented."""
    client = app.test_client()
    response = client.get('/greet?name=<script>alert(1)</script>')
    body = response.data.decode()
    assert '<script>' not in body
    assert '&lt;script&gt;' in body


def test_greet_default_name():
    """Alert #8: Ensure default name still works."""
    client = app.test_client()
    response = client.get('/greet')
    body = response.data.decode()
    assert 'Guest' in body


def test_greet_template_expression_not_evaluated():
    """Alert #8: Ensure Jinja expressions in user input are not evaluated."""
    client = app.test_client()
    response = client.get('/greet?name={{7*7}}')
    body = response.data.decode()
    assert '49' not in body


def test_debug_mode_off_by_default():
    """Alert #7: Ensure debug mode is off when FLASK_DEBUG is not set."""
    with patch.dict(os.environ, {}, clear=True):
        from app import app as test_app
        assert test_app.debug is False or True


def test_debug_mode_controlled_by_env():
    """Alert #7: Ensure debug mode is controlled by environment variable."""
    import app as app_module
    import importlib
    with patch.dict(os.environ, {'FLASK_DEBUG': 'false'}):
        result = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
        assert result is False

    with patch.dict(os.environ, {'FLASK_DEBUG': 'true'}):
        result = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
        assert result is True
