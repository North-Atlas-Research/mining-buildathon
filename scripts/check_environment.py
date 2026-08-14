from pathlib import Path

from mining_sprint.paths import (
    cache_dir,
    interim_dir,
    outputs_dir,
    processed_dir,
    raw_dir,
    scratch_dir,
)


def main() -> None:
    directories = {
        "Raw": raw_dir(),
        "Interim": interim_dir(),
        "Processed": processed_dir(),
        "Outputs": outputs_dir(),
        "Scratch": scratch_dir(),
        "Cache": cache_dir(),
    }

    failed = False
    for name, path in directories.items():
        exists = path.exists()
        writable = path.exists() and path.is_dir() and _is_writable(path)
        expected_writable = name != "Raw"

        print(
            f"{name:10} {path} "
            f"exists={exists} writable={writable} expected_writable={expected_writable}"
        )

        if not exists or writable != expected_writable:
            failed = True

    if failed:
        raise SystemExit("Environment validation failed.")


def _is_writable(path: Path) -> bool:
    probe = path / ".write_probe"
    try:
        probe.write_text("probe")
        probe.unlink()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    main()
