"""Meta Graph, Instagram, and Marketing API source adapter."""

from .auth import MetaConfig
from .client import MetaAPIError, MetaClient

__all__ = ["MetaAPIError", "MetaClient", "MetaConfig"]
