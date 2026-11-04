import json

import pytest

from fitbit_osc.config import Config, build_parser, load_config, merge, parse_port, save_config


def write(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(p)


def test_missing_file_gives_defaults(tmp_path):
    cfg, warnings = load_config(str(tmp_path / "nope.json"))
    assert cfg == Config() and warnings == []


def test_values_are_loaded(tmp_path):
    cfg, warnings = load_config(write(tmp_path, {"chatbox": True, "min": 40, "max": 200, "port": 9001}))
    assert cfg.chatbox and (cfg.min, cfg.max, cfg.port) == (40, 200, 9001) and warnings == []


def test_bad_values_fall_back_with_warnings(tmp_path):
    cfg, warnings = load_config(write(tmp_path, {"chatbox": "yes", "min": "40", "port": 70000, "colour": 1}))
    assert cfg == Config()
    assert len(warnings) == 4 and any("colour" in w for w in warnings)


def test_min_must_be_below_max(tmp_path):
    cfg, warnings = load_config(write(tmp_path, {"min": 200, "max": 100}))
    assert (cfg.min, cfg.max) == (0, 255) and warnings


def test_broken_json_and_bom(tmp_path):
    cfg, warnings = load_config(write(tmp_path, "{not json"))
    assert cfg == Config() and warnings
    p = tmp_path / "bom.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"chatbox": True}).encode())  # Notepad speichert gern mit BOM
    assert load_config(str(p))[0].chatbox


def test_save_roundtrip(tmp_path):
    p = str(tmp_path / "config.json")
    save_config(Config(chatbox=True, port=9002), p)
    assert load_config(p)[0] == Config(chatbox=True, port=9002)


def test_parse_port():
    assert parse_port("auto") == "auto" and parse_port("AUTO") == "auto"
    assert parse_port("9000") == 9000
    for bad in ("0", "65536", "x", True):
        with pytest.raises(ValueError):
            parse_port(bad)


def test_command_line_overrides_only_given_options():
    file_cfg = Config(chatbox=True, max=200)
    ns = build_parser().parse_args(["--port", "9001", "--min", "40"])
    cfg, warnings = merge(file_cfg, ns)
    assert (cfg.port, cfg.min, cfg.max, cfg.chatbox) == (9001, 40, 200, True) and warnings == []
    assert file_cfg.port == "auto"  # Datei-Einstellungen bleiben unberührt


def test_runtime_flags_parse():
    ns = build_parser().parse_args(["--demo", "--tray", "--follow-steamvr", "--overlay"])
    assert ns.demo and ns.tray and ns.follow_steamvr and ns.overlay
