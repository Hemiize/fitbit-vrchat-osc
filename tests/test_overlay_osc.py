import json
import socket
import urllib.request

from fitbit_osc.osc import OscSender
from fitbit_osc.overlay import Overlay

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def test_overlay_serves_page_and_json():
    state = {"bpm": 72, "active": True, "connected": True, "battery": 50}
    ov = Overlay(lambda: state, 0)  # Port 0: freien Port nehmen
    url = ov.start()
    try:
        page = opener.open(url, timeout=5).read().decode()
        assert "hr.json" in page
        data = json.load(opener.open(url + "hr.json", timeout=5))
        assert data == state
        try:
            opener.open(url + "nope", timeout=5)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        ov.stop()
    assert not ov.running


def test_sender_reaches_udp_listener_and_follows_target_change():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(2)
    s = OscSender("127.0.0.1", 9)
    s.target = ("127.0.0.1", rx.getsockname()[1])  # wie nach einem OSCQuery-Treffer
    s.send("/avatar/parameters/HR", 80)
    data, _ = rx.recvfrom(1024)
    assert data.startswith(b"/avatar/parameters/HR\0")
    s.close()
    rx.close()
