import pytest

from camcontrol.hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey


def test_parses_modifiers_and_letter():
    mods, vk = parse_hotkey("ctrl+alt+h")
    assert mods == MOD_CONTROL | MOD_ALT
    assert vk == ord("H")


def test_bare_key_has_no_modifiers():
    mods, vk = parse_hotkey("h")
    assert mods == 0
    assert vk == ord("H")


def test_shift_and_digit():
    mods, vk = parse_hotkey("ctrl+shift+1")
    assert mods == MOD_CONTROL | MOD_SHIFT
    assert vk == ord("1")


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+nope")
