from fitbit_osc.bridge import FRESH, Bridge
from fitbit_osc.config import Config


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make():
    sent = []
    clock = Clock()
    changes = []
    b = Bridge(Config(), lambda addr, *v: sent.append((addr.rsplit("/", 1)[-1], v[0])), clock,
               on_change=lambda: changes.append(1))
    return b, sent, clock, changes


def last(sent, name):
    return [v for n, v in sent if n == name][-1]


def test_reset_turns_everything_off():
    b, sent, _, _ = make()
    b.reset()
    assert last(sent, "Enabled") is False and last(sent, "isHRActive") is False
    assert last(sent, "isHRConnected") is False


def test_value_makes_avatar_active():
    b, sent, _, changes = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    assert last(sent, "Value") == 72 and last(sent, "isHRActive") is True
    assert b.fresh() and b.active and changes


def test_stale_value_turns_avatar_inactive_once():
    b, sent, clock, _ = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    clock.t += FRESH + 0.1
    sent.clear()
    b.tick()
    assert ("isHRActive", False) in sent and ("Enabled", False) in sent
    sent.clear()
    b.tick()
    assert sent == []  # nur einmal melden


def test_fresh_value_after_stale_reactivates_and_notifies():
    b, sent, clock, changes = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    clock.t += FRESH + 1
    b.tick()
    changes.clear()
    b.handle(bytes([0, 72]))  # gleicher Wert wie vorher
    assert b.active and changes  # Tray wird trotzdem wieder rot


def test_zero_bpm_and_no_contact_deactivate():
    b, sent, _, _ = make()
    b.set_connected(True)
    b.handle(bytes([0, 70]))
    b.handle(bytes([0, 0]))
    assert not b.active and b.bpm == 0 and last(sent, "isHRActive") is False
    b.handle(bytes([0, 70]))
    b.handle(bytes([0x04, 70]))  # Kontakt-Status unterstützt, aber kein Kontakt
    assert not b.active and not b.fresh()


def test_zero_keeps_connection_alive_for_stale_check():
    b, _, clock, _ = make()
    b.set_connected(True)
    clock.t += 10
    b.handle(bytes([0, 0]))
    assert b.seen == clock.t


def test_disconnect_turns_off():
    b, sent, _, _ = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    b.set_connected(False)
    assert last(sent, "isHRConnected") is False and last(sent, "isHRActive") is False
    assert b.status_text() == "No band connected"


def test_battery_and_status_text():
    b, sent, _, _ = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    b.set_battery(64)
    assert last(sent, "HRBattery") == 0.64
    assert b.status_text() == "Heart rate: 72 BPM | battery 64 %"
    b.set_battery(250)
    assert b.battery == 100


def test_snapshot_hides_stale_bpm():
    b, _, clock, _ = make()
    b.set_connected(True)
    b.handle(bytes([0, 72]))
    assert b.snapshot()["bpm"] == 72 and b.snapshot()["active"]
    clock.t += FRESH + 1
    assert b.snapshot() == {"bpm": 0, "active": False, "connected": True, "battery": None}
