def unsapported_log_level_value_error(
    log_level: str,
    expected: frozenset[str],
) -> ValueError:
    return ValueError(
        f"Unsupported log level: {log_level!r}. Expected one of: {', '.join(sorted(expected))}"
    )
