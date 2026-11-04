import struct

from fitbit_osc.protocol import encode_osc, hr_params, parse_hr, percent


def decode_osc(msg: bytes):
    """Minimaler OSC-Decoder als Gegenprobe zu encode_osc."""
    def string(pos):
        end = msg.index(b"\0", pos)
        s = msg[pos:end].decode()
        return s, (end + 4) & ~3
    address, pos = string(0)
    tags, pos = string(pos)
    values = []
    for t in tags[1:]:
        if t == "i":
            values.append(struct.unpack(">i", msg[pos:pos + 4])[0])
            pos += 4
        elif t == "f":
            values.append(struct.unpack(">f", msg[pos:pos + 4])[0])
            pos += 4
        elif t == "s":
            s, pos = string(pos)
            values.append(s)
        elif t in "TF":
            values.append(t == "T")
    assert pos == len(msg)
    return address, values


def test_uint8_bpm():
    m = parse_hr(bytes([0x00, 72]))
    assert m.bpm == 72 and m.contact is None and m.rr_ms == []


def test_uint16_bpm():
    m = parse_hr(bytes([0x01, 0x2C, 0x01]))  # 300 als UINT16 little endian
    assert m.bpm == 300


def test_short_packets_are_rejected():
    assert parse_hr(b"") is None
    assert parse_hr(b"\x00") is None
    assert parse_hr(b"\x01\x50") is None  # UINT16 angekündigt, nur ein Byte da


def test_contact_flags():
    assert parse_hr(bytes([0x06, 70])).contact is True  # unterstützt + Kontakt
    assert parse_hr(bytes([0x04, 70])).contact is False  # unterstützt, kein Kontakt
    assert parse_hr(bytes([0x02, 70])).contact is None  # nicht unterstützt


def test_energy_and_rr_intervals():
    # Flags: Energie (0x08) + RR (0x10); Puls 60, Energie 500 kJ, RR 1024 und 512 (1/1024 s)
    data = bytes([0x18, 60]) + (500).to_bytes(2, "little") + (1024).to_bytes(2, "little") + (512).to_bytes(2, "little")
    m = parse_hr(data)
    assert m.bpm == 60 and m.energy_kj == 500
    assert m.rr_ms == [1000.0, 500.0]


def test_rr_without_energy_and_odd_trailing_byte():
    data = bytes([0x10, 80]) + (1024).to_bytes(2, "little") + b"\x07"
    assert parse_hr(data).rr_ms == [1000.0]


def test_encode_osc_roundtrip():
    msg = encode_osc("/avatar/parameters/HR", 72)
    assert len(msg) % 4 == 0
    assert decode_osc(msg) == ("/avatar/parameters/HR", [72])
    addr, vals = decode_osc(encode_osc("/chatbox/input", "❤ 72 BPM", True, False))
    assert addr == "/chatbox/input" and vals == ["❤ 72 BPM", True, False]
    _, vals = decode_osc(encode_osc("/x", 0.5))
    assert vals == [0.5]


def test_string_padding_always_terminates():
    # Länge genau durch 4 teilbar braucht trotzdem vier Nullbytes
    assert encode_osc("/abc")[:8] == b"/abc\0\0\0\0"


def test_percent_and_params():
    assert percent(40, 40, 200) == 0.0
    assert percent(200, 40, 200) == 1.0
    assert percent(300, 40, 200) == 1.0
    assert percent(10, 40, 200) == 0.0
    params = dict(hr_params(123, 0, 255))
    assert params["VRCOSC/Heartrate/Value"] == 123
    assert (params["onesHR"], params["tensHR"], params["hundredsHR"]) == (3, 2, 1)
    assert params["isHRActive"] is True and params["isHRConnected"] is True
    assert abs(params["FullHRPercent"] - (123 / 255 * 2 - 1)) < 1e-9


def test_int_params_are_clamped_for_vrchat():
    params = dict(hr_params(300, 0, 255))
    assert params["VRCOSC/Heartrate/Value"] == 255 and params["HR"] == 255
