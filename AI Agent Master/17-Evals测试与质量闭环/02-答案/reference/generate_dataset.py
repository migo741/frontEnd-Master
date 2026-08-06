from pathlib import Path

from solution import build_dataset, to_jsonl


target = Path(__file__).with_name("dataset.jsonl")
target.write_text(to_jsonl(build_dataset(100)), encoding="utf-8")
print(f"wrote 100 eval cases to {target}")

