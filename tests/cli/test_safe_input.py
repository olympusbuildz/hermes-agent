"""Regression: bare input() must not see modifyOtherKeys escapes (#97975)."""

from __future__ import annotations


class _FakeOutput:
    """Minimal output stream matching _enable_extended_enter_keys write path."""

    def __init__(self):
        self.written = []

    def write_raw(self, data):
        self.written.append(data if isinstance(data, str) else data.decode())

    def flush(self):
        pass


def test_safe_input_resets_modes_and_returns_clean_string(monkeypatch):
    """While extended keys are active, input() resets modes around the read.

    Without the reset, Shift+A under modifyOtherKeys level 2 arrives as
    ``ESC[27;2;65~`` instead of ``A``.  After the reset, the terminal sends
    the clean character — which is what the wrapped builtin must return.
    """
    import cli as cli_mod

    out = _FakeOutput()
    cli_mod._extended_enter_keys_active = True
    cli_mod._extended_enter_keys_output = out

    dirty = "\x1b[27;2;65~"  # Shift+A under modifyOtherKeys=2
    clean = "A"

    def fake_builtin(prompt=""):
        # Modes must already be reset before the builtin read runs.
        assert any(
            cli_mod._TERMINAL_INPUT_MODE_RESET_SEQ in chunk for chunk in out.written
        ), "expected terminal mode reset before builtin input()"
        # Simulate the post-reset terminal: clean char, not the raw escape.
        assert dirty  # document the leaked form we are guarding against
        return clean

    monkeypatch.setattr(cli_mod, "_BUILTIN_INPUT", fake_builtin)
    # Re-enable would call the real allowlist/TTY path; stub it so the test
    # stays hermetic and we can assert it was invoked after the read.
    reenable_calls = []

    def fake_enable(output=None, env=None):
        reenable_calls.append(output)
        cli_mod._extended_enter_keys_active = True
        cli_mod._extended_enter_keys_output = output
        return True

    monkeypatch.setattr(cli_mod, "_enable_extended_enter_keys", fake_enable)

    try:
        result = cli_mod._safe_input("prompt: ")
        assert result == clean
        assert dirty not in result
        assert reenable_calls == [out]
        assert any(
            cli_mod._TERMINAL_INPUT_MODE_RESET_SEQ in chunk for chunk in out.written
        )
    finally:
        cli_mod._extended_enter_keys_active = False
        cli_mod._extended_enter_keys_output = None
