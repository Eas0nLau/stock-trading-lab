from pathlib import Path

from stock_lab.infrastructure.tdx.client import TdxClientSession


def test_tdx_client_session_closes_fake_client():
    class Client:
        def close(self):
            self.closed = True

    client = Client()
    session = TdxClientSession(Path("C:/tdx"))
    session.tq = client
    session.__exit__(None, None, None)

    assert client.closed is True
