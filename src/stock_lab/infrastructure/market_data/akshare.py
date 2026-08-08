class AkShareSource:
    def fetch_index_daily(self):
        import akshare

        return akshare.stock_zh_index_daily(symbol="sh000001")
