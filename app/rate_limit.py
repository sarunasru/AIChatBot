"""Shared rate limiter, used by main.py (setup) and routes.py (per-route limits)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
