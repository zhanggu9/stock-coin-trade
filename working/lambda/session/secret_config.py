import os


def environment_values(keys: tuple[str, ...]) -> dict[str, str]:
    values = {key: os.environ.get(key) for key in keys}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"환경변수 누락: {', '.join(missing)}")
    return {key: values[key] for key in keys}
