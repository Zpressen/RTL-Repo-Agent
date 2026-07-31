from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys
import tempfile
import traceback


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: system_verify_wrapper.py <verify_script> <generated_dir> <output_dir>", file=sys.stderr)
        return 2
    verify_script = pathlib.Path(sys.argv[1]).resolve()
    generated_dir = pathlib.Path(sys.argv[2]).resolve()
    output_dir = pathlib.Path(sys.argv[3]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    created_dirs: list[pathlib.Path] = []
    original_temporary_directory = tempfile.TemporaryDirectory

    class KeepTemporaryDirectory:
        def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False, delete=True):
            del ignore_cleanup_errors, delete
            self.name = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
            created_dirs.append(pathlib.Path(self.name))

        def __enter__(self):
            return self.name

        def __exit__(self, exc_type, exc, tb):
            return False

        def cleanup(self):
            return None

    tempfile.TemporaryDirectory = KeepTemporaryDirectory
    try:
        spec = importlib.util.spec_from_file_location("_zerorepo_system_verify", verify_script)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not import verifier: {verify_script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verify_system = getattr(module, "verify_system", None)
        if verify_system is None:
            raise RuntimeError(f"Verifier does not expose verify_system(generated_dir): {verify_script}")
        passed, message = verify_system(str(generated_dir))
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        tempfile.TemporaryDirectory = original_temporary_directory

    copied_vcd = False
    for temp_dir in created_dirs:
        try:
            for candidate in temp_dir.rglob("wave.vcd"):
                shutil.copy2(candidate, output_dir / "wave.vcd")
                print(f"ZEROREPO_VCD_COPIED: {candidate} -> {output_dir / 'wave.vcd'}")
                copied_vcd = True
                break
        except OSError:
            pass
        if copied_vcd:
            break

    for temp_dir in created_dirs:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(message)
    print("Summary:")
    print(f"  system_verify: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
