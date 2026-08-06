from pathlib import Path

from solution import eval_jsonl


target = Path(__file__).with_name("capstone_eval_150.jsonl")
target.write_text(eval_jsonl(150), encoding="utf-8")
print(f"wrote 150 capstone cases to {target}")

