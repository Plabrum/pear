"""STUB push service — logs instead of delivering.

TODO(Phase 6): implement direct APNs delivery using `config.APNS_KEY` /
`APNS_KEY_ID` / `APNS_TEAM_ID` (the .p8 token signer) and per-device tokens
stored on the user/profile. The `send` signature here is the contract Phase-6
fills in and that the actions layer already depends on.
"""

import logging

logger = logging.getLogger(__name__)


class PushService:
    """Minimal push-notification client.

    `send` mirrors the eventual production signature so actions written now keep
    working once Phase 6 swaps the implementation.
    """

    async def send(self, token: str, title: str, body: str) -> None:
        logger.info("PUSH (stub, not delivered) -> token=%s title=%r body=%r", token, title, body)
