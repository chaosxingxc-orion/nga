"""Raw-completion SFT dataset for round R3 (R3-SFT-PREREG §3.1, §7.2).

Differs from the task-4 driver's `raw_sft_dataset.py` (/mnt/cephfs/xingchao/docker/verl_v030_20261029/code/
raw_sft_dataset.py) in the one place that round's prereg rules on: that dataset appends EOS and puts it in the
loss ("the answer tokens plus EOS are the loss target"); §7.2 here requires **no EOS token in the loss** ("if the
framework appends one it is masked"). This class never appends EOS at all, which is the simplest way to satisfy
that and matches the evaluation scorer (r0_code/scorer.py HFScorer._encode), which also never appends EOS: the
identifier's own tokens are exactly what is scored, nothing after them.

Reads the JSONL rows written by build_kev_sft.py: {"prompt": str, "response": " " + gold name, ...}. One row = one
training example (one question), per prereg §3.3(e) ("one training example per question, not per record").
input_ids = tokens(prompt) + tokens(response); loss_mask = 0 on the prompt tokens, 1 on the response tokens.
Left-truncation (dropping early input, keeping the prompt tail and all of the response) if a row exceeds
max_length; a counter of truncated/response-clipped rows is kept on the dataset instance for the launcher to log.
"""
import json

import torch
from torch.utils.data import Dataset


class R3RawCompletionDataset(Dataset):
    def __init__(self, parquet_files, tokenizer, config, processor=None, max_samples=-1):
        files = [parquet_files] if isinstance(parquet_files, str) else list(parquet_files)
        rows = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        if max_samples and max_samples > 0:
            rows = rows[:max_samples]
        self.rows, self.tok = rows, tokenizer
        self.max_length = config.get("max_length", 2048)
        self.n_truncated = 0
        self.n_response_clipped = 0

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        p = self.tok(r["prompt"], add_special_tokens=False)["input_ids"]
        a = self.tok(r["response"], add_special_tokens=False)["input_ids"]
        ids = p + a
        if len(ids) > self.max_length:
            self.n_truncated += 1
            if len(a) > self.max_length:  # pathological; keep the loss region, drop nothing from it
                a = a[-self.max_length:]
                self.n_response_clipped += 1
            p = p[-(self.max_length - len(a)):]
            ids = p + a
        loss = [0] * len(p) + [1] * len(a)
        input_ids = torch.tensor(ids, dtype=torch.long)
        return {"input_ids": input_ids, "position_ids": torch.arange(len(ids), dtype=torch.long),
                "loss_mask": torch.tensor(loss, dtype=torch.long)}
