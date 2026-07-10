from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.domain.contacts.service import ContactService
from app.utils.deps import dep


@dep("contact_service", sync_to_thread=False)
def provide_contact_service(transaction: AsyncSession) -> ContactService:
    return ContactService(db=transaction, config=config)
