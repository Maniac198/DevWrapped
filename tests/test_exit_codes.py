from devwrapped.exit_codes import ExitCode


def test_exit_code_values_stable():
    # This is part of the CLI contract; breaking these is a breaking change.
    assert ExitCode.OK == 0
    assert ExitCode.USAGE_ERROR == 1
    assert ExitCode.AUTH_FAILURE == 2
    assert ExitCode.NO_DATA == 3
    assert ExitCode.RATE_LIMITED == 4
    assert ExitCode.INTERNAL == 10
