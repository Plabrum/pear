"""State machine dependency providers."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.state_machine.machine import StateMachineService
from app.utils.deps import dep


@dep("sm_service")
def provide_sm_service(transaction: AsyncSession) -> StateMachineService:
    return StateMachineService(transaction)
