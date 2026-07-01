"""STUB push-notification service (Phase 2).

Pear's real push delivery (direct APNs via the .p8 key in `config.APNS_*`) lands
in Phase 6. This package provides a minimal `PushService` so the actions layer
(`ActionDeps.push`) and DI wiring (`@dep("push")`) resolve today. In dev/test it
logs instead of delivering.
"""
