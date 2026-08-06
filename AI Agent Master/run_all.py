"""逐章运行标准答案测试；每章独立进程，避免同名 solution 模块冲突。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    tests = sorted(ROOT.glob("*/02-答案/reference/test_solution.py"))
    if len(tests) != 22:
        print(f"ERROR: 期望 22 个测试文件，实际 {len(tests)}", file=sys.stderr)
        return 2

    failed: list[Path] = []
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for index, test in enumerate(tests, 1):
        chapter = test.parents[2].name
        print(f"\n[{index:02d}/22] {chapter}")
        result = subprocess.run(
            [sys.executable, str(test)],
            cwd=test.parent,
            env=env,
            check=False,
        )
        if result.returncode:
            failed.append(test)

    if failed:
        print("\n失败章节：", file=sys.stderr)
        for path in failed:
            print(f"- {path.parents[2].name}", file=sys.stderr)
        return 1

    print("\nOK: 22 章标准答案测试全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

