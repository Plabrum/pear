# A monotonic fake-id generator for unit tests.
#
# Replaces the old `uuid4()` test ids now that primary keys are int-backed Sqids.
# Returns distinct, high `Sqid` values (well above the small autoincrement ids the
# seed fixtures create) so a fake id never collides with a real row and inequality
# assertions hold.

import itertools

from app.utils.sqids import Sqid

_counter = itertools.count(900_000_000)


def fake_id() -> Sqid:
    return Sqid(next(_counter))
