import time
import threading

# Import your real class
from scanner.ibkr_signal_engine import IBapi


class FakeIBapi(IBapi):
    """
    Stubbed IBapi that simulates IB responses.
    No socket, no real EClient usage.
    """

    def __init__(self, mode):
        # do NOT call real EClient init
        super().__init__()
        self.mode = mode

        # minimal fields used by getDataResult
        self.data = {}
        self.hisdtId = {}
        self.requestInformation = {}
        self.errorSymbol = {}
        self.warningTicker = {}
        self.contract_cache = {}
        self.numberOfTicker = 1
        self.maxlength = 1
        self.initial = 0
        self.Locking = threading.Lock()

        # fake config
        class Cfg:
            contract_lookup_timeout_sec = 1.0
            contract_lookup_poll_sec = 0.1
            contract_lookup_max_attempts = 2
            history_lookup_timeout_sec = 1.0
            history_lookup_poll_sec = 0.1

        self.config = Cfg()

    # ---------------------------
    # STUB IB methods
    # ---------------------------

    def findContractDetails(self, req_id, cusip, sec_type, symbol):

        self.requestInformation[req_id] = False
        self.data[req_id] = []

        def delayed_response():
            time.sleep(0.2)

            # SUCCESS PATH
            if self.mode == "success":
                self.data[req_id] = [
                    {
                        "symbol": symbol,
                        "secType": "STK",
                        "exchange": "SMART",
                        "primaryExchange": "NASDAQ",
                        "currency": "USD",
                    }
                ]
                self.requestInformation[req_id] = True

            # FAIL PATH (never sets requestInformation True)
            elif self.mode == "fail":
                pass

        threading.Thread(target=delayed_response).start()

    def getData(self, contract, form, theid):
        # immediately simulate historical data
        self.hisdtId[theid] = True
        self.HistoricalDt = {theid: [[0, 1, 1, 1, 1, 100]]}

    def cancelMktData(self, *args, **kwargs):
        pass

    # override heavy parts
    def getIndicators(self, *args, **kwargs):
        return {"cusip": "TEST", "close": 1}

    def buySellSignalCheck(self, data, form):
        return data


def run_case(mode):
    print("\n==============================")
    print("Running case:", mode)
    print("==============================")

    api = FakeIBapi(mode)

    api.getDataResult(
        i="123456789",
        m="AAPL",
        net_position={"123456789": 0},
        form={},
        theid=1
    )

    print("warningTicker:", api.warningTicker)
    print("contract_cache:", api.contract_cache)


if __name__ == "__main__":
    run_case("success")
    run_case("fail")
