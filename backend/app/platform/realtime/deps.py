from litestar.channels import ChannelsPlugin

from app.platform.realtime.service import RealtimeService
from app.utils.deps import dep


@dep("realtime", sync_to_thread=False)
def provide_realtime(channels: ChannelsPlugin) -> RealtimeService:
    return RealtimeService(channels)
