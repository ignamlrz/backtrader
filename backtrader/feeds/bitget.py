from ..feeds import live
from .. import feed
from .. import stores

class BitgetLiveData(live.GenericOhlcviLiveData):

    params = dict(limit=200)
    
    plotinfo = dict(plotlog=True)

    def __init__(self, **kwargs):
        super(BitgetLiveData, self).__init__(**kwargs)
        self.exchange_config = kwargs.get('config', {})
        self.store = None

    def get_store(self):
        """Returns this data as a store"""
        if not self.store:
            self.store = stores.BitgetStore(config=self.exchange_config)
        return self.store

    def notify_live_data(self, data):
        """Notify the live data"""


class BitgetLive(feed.FeedBase):
    """Feed of Bitget live data"""

    DataCls = BitgetLiveData
