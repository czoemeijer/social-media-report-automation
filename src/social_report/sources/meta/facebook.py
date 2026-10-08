"""Required Facebook Page identity and Instagram relationship reads."""

from __future__ import annotations

from typing import Any, Mapping

from .client import MetaClient


def get_page(client: MetaClient, page_id: str) -> Mapping[str, Any]:
    return client.get(
        page_id,
        {"fields": "id,name,instagram_business_account{id,username}"},
    )
