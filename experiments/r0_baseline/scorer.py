"""Scorers: a batch of items in, one probability distribution per item out.

Interface.  ``Scorer.score(items)`` takes a list of normalized records (common.load_records) and
returns, per item, a list of probabilities aligned with ``item["levels"]`` (so the distribution is
over that item's declared level ids, in declared order).  ``Scorer.fit(train_view)`` is a no-op
except for the constant classifier, which accepts a ``split.TrainView`` and nothing else.

Implementations: HFScorer (the real readout), EmptyInputScorer and QuestionOnlyScorer (prompt
transforms over any inner scorer), ConstantClassifierScorer, UniformScorer, MockScorer.
"""
import hashlib
import math
from collections import Counter, defaultdict

import split as split_mod
from common import FLOOR_VARIANT
from prompt import RENDER_MODES, blank_input, build_prompt, drop_input


def softmax(scores):
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    z = math.fsum(exps)
    return [e / z for e in exps]


class Scorer:
    name = "scorer"

    def fit(self, train):
        return None

    def score(self, items):
        raise NotImplementedError

    def describe(self):
        return {"scorer": self.name}


# --------------------------------------------------------------------------------------------
# Degenerate baselines (pre-registration section 4)
# --------------------------------------------------------------------------------------------

class UniformScorer(Scorer):
    """Item 4: equal mass on every level."""
    name = "uniform"

    def score(self, items):
        return [[1.0 / len(it["levels"])] * len(it["levels"]) for it in items]


class ConstantClassifierScorer(Scorer):
    """Item 3: always the majority level of the question, fitted on the train split only.

    The majority is counted on gold-trusted floor rows (T1 ``original``, T2 ``base``) of the train
    side, per (source, qname).  A question never seen in train (every held-out question under the
    question-disjoint split) falls back to the most common gold id among train items of the same
    (source, level-id tuple), then to the first level.  The output is a one-hot distribution.
    """

    def __init__(self, splitter_name):
        self.splitter_name = splitter_name
        self.name = f"constant@{splitter_name}"
        self._by_question = {}
        self._by_idset = {}
        self._fitted = False

    def fit(self, train):
        if not isinstance(train, split_mod.TrainView):
            raise TypeError("ConstantClassifierScorer.fit needs a split.TrainView")
        if train.splitter.name != self.splitter_name:
            raise ValueError("TrainView belongs to a different split than this classifier")
        by_q, by_ids = defaultdict(Counter), defaultdict(Counter)
        for r in train.rows:
            gold = r.get("gold_id", r.get("gold"))
            if gold is None or r["variant"] != FLOOR_VARIANT[r["task"]]:
                continue
            ids = tuple(l["id"] for l in r["levels"]) if "levels" in r else tuple(r["ids"])
            by_q[(r["source"], r["qname"])][gold] += 1
            by_ids[(r["source"], tuple(sorted(ids)))][gold] += 1
        self._by_question = {k: self._majority(c) for k, c in by_q.items()}
        self._by_idset = {k: self._majority(c) for k, c in by_ids.items()}
        self._fitted = True

    @staticmethod
    def _majority(counter):
        """Most common id; ties go to the smaller id so the result does not depend on file order."""
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def majority_for(self, item):
        ids = [l["id"] for l in item["levels"]]
        choice = self._by_question.get((item["source"], item["qname"]))
        if choice is None:
            choice = self._by_idset.get((item["source"], tuple(sorted(ids))))
        return choice if choice in ids else ids[0]

    def score(self, items):
        if not self._fitted:
            raise RuntimeError("fit the constant classifier on a TrainView first")
        out = []
        for it in items:
            m = self.majority_for(it)
            out.append([1.0 if l["id"] == m else 0.0 for l in it["levels"]])
        return out

    def describe(self):
        return {"scorer": self.name, "questions_fitted": len(self._by_question)}


class _TransformScorer(Scorer):
    """Applies a prompt transform to every item and delegates to an inner scorer."""
    suffix = ""
    transform = None

    def __init__(self, inner):
        self.inner = inner
        self.name = f"{inner.name}+{self.suffix}"

    def fit(self, train):
        return self.inner.fit(train)

    def score(self, items):
        return self.inner.score([type(self).transform(it) for it in items])

    def describe(self):
        return {"scorer": self.name, "inner": self.inner.describe()}


class EmptyInputScorer(_TransformScorer):
    """Item 1: the input is replaced by an empty string; everything else identical."""
    suffix = "empty_input"
    transform = staticmethod(blank_input)


class QuestionOnlyScorer(_TransformScorer):
    """Item 2: the input is dropped; question and level set kept."""
    suffix = "question_only"
    transform = staticmethod(drop_input)


# --------------------------------------------------------------------------------------------
# Mock scorer for testing the pipeline without a model
# --------------------------------------------------------------------------------------------

def _unit_noise(*parts):
    """Deterministic pseudo-random number in [-1, 1) from the given strings."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 63 - 1.0


class MockScorer(Scorer):
    """Deterministic fake readout. The logit of a level is the sum of four terms:

    * ``definition_weight`` * noise(input, question, definition): follows definitions, ignores names;
    * ``name_weight`` * noise(input, question, name): follows names, ignores definitions;
    * ``random_weight`` * noise(item key, level id): seeded by item id, no structure at all;
    * ``signal`` * [level is gold]: an oracle, for exercising the accuracy path.

    Presets: ``invariant()`` is perfectly name-invariant and follows definition swaps;
    ``name_driven()`` is perfectly name-driven and ignores definitions; ``random()`` is structureless;
    ``oracle()`` always puts its mass on gold.  Logits are scaled by ``sharpness`` so that most
    distributions are decisive under the cumulative-mass operator.
    """

    def __init__(self, name="mock", definition_weight=0.0, name_weight=0.0, random_weight=0.0,
                 signal=0.0, sharpness=6.0, prefix_weight=0.0):
        self.name = name
        self.definition_weight = definition_weight
        self.name_weight = name_weight
        self.random_weight = random_weight
        self.signal = signal
        self.sharpness = sharpness
        self.prefix_weight = prefix_weight  # follows the T3 prefix questions (order included)

    @classmethod
    def invariant(cls):
        return cls("mock-invariant", definition_weight=1.0)

    @classmethod
    def name_driven(cls):
        return cls("mock-name-driven", name_weight=1.0)

    @classmethod
    def prefix_driven(cls):
        return cls("mock-prefix-driven", definition_weight=1.0, prefix_weight=1.0)

    @classmethod
    def random(cls):
        return cls("mock-random", random_weight=1.0)

    @classmethod
    def oracle(cls):
        return cls("mock-oracle", signal=1.0, sharpness=1.0)

    def _logits(self, it):
        base = (it["input"], it["question"])
        out = []
        for l in it["levels"]:
            z = 0.0
            if self.definition_weight:
                z += self.definition_weight * _unit_noise("def", *base, l["definition"])
            if self.name_weight:
                z += self.name_weight * _unit_noise("name", *base, l["name"])
            if self.random_weight:
                z += self.random_weight * _unit_noise("rand", it["key"], l["id"])
            if self.prefix_weight:
                z += self.prefix_weight * _unit_noise("prefix", *base, l["definition"], "\x1e".join(it.get("prefix_questions") or []))
            z *= self.sharpness
            if self.signal and l["id"] == it.get("gold_id"):
                z += self.signal * 8.0
            out.append(z)
        return out

    def score(self, items):
        return [softmax(self._logits(it)) for it in items]

    def describe(self):
        return {"scorer": self.name, "definition_weight": self.definition_weight,
                "name_weight": self.name_weight, "random_weight": self.random_weight,
                "signal": self.signal, "sharpness": self.sharpness}


# --------------------------------------------------------------------------------------------
# Same-backbone label log-probability readout
# --------------------------------------------------------------------------------------------

class HFScorer(Scorer):
    """Label log-probability readout with a Hugging Face decoder (pre-reg section 1, E-0.3).

    For each item one prompt is built (prompt.build_prompt, raw completion, no chat template).  Each level is scored by the summed
    log-probability of its identifier tokens given the prompt; the scores are normalized with a
    softmax over the item's level set.  Prompt and identifier are tokenized separately and the ids
    concatenated, so the scored tokens are exactly the identifier's tokens.  No chat template and
    no special tokens are added.

    Works with transformers 4.57.x and 5.x: the dtype keyword and the model class lookup branch on
    the installed major version.  Rows are left-padded and only the logits of the identifier
    positions are computed (``logits_to_keep``), because the vocabulary of the Qwen3.5 family is
    about 248k entries and full logits would not fit.

    NOT exercised in the CPU validation of this repository (no torch there); run the smoke command
    in the run_baseline.py docstring before relying on it.
    """

    def __init__(self, model_path, device="cpu", dtype="auto", render="record_name",
                 token_budget=16384, name="hf", model=None, tokenizer=None):
        if render not in RENDER_MODES:
            raise ValueError(f"render must be one of {RENDER_MODES}")
        self.model_path = model_path
        self.device = device
        self.dtype = dtype
        self.render = render
        self.token_budget = token_budget
        self.name = name
        self._model = model
        self._tok = tokenizer

    # ---- loading -------------------------------------------------------------------------
    def _load(self):
        if self._model is not None:
            return
        import torch
        import transformers

        major = int(transformers.__version__.split(".")[0])
        if self.device.startswith("npu"):
            import torch_npu  # noqa: F401  (registers the npu device)
        dtype_name = self.dtype
        if dtype_name == "auto":
            dtype_name = "float32" if self.device == "cpu" else "bfloat16"
        torch_dtype = getattr(torch, dtype_name)
        dtype_kw = {"dtype": torch_dtype} if major >= 5 else {"torch_dtype": torch_dtype}

        self._tok = transformers.AutoTokenizer.from_pretrained(self.model_path)
        model, info = None, None
        # The Qwen3.5 checkpoint is a multimodal wrapper; try the causal-LM mapping first, then the
        # image-text-to-text class, and refuse to continue if any weight failed to load.
        for cls_name in ("AutoModelForCausalLM", "AutoModelForImageTextToText"):
            cls = getattr(transformers, cls_name, None)
            if cls is None:
                continue
            try:
                model, info = cls.from_pretrained(self.model_path, output_loading_info=True, **dtype_kw)
            except (ValueError, KeyError):
                continue
            if not info.get("missing_keys"):
                break
            model = None
        if model is None:
            raise RuntimeError(
                f"could not load {self.model_path} with a complete weight set under transformers "
                f"{transformers.__version__} (last loading info: {info})")
        self._model = model.to(self.device).eval()

    # ---- scoring -------------------------------------------------------------------------
    def _encode(self, item):
        p = build_prompt(item, self.render)
        prefix = self._tok(p.text, add_special_tokens=False)["input_ids"]
        cand_ids = [self._tok(c, add_special_tokens=False)["input_ids"] for c in p.candidates]
        if any(len(c) == 0 for c in cand_ids):
            raise ValueError("a level identifier tokenized to nothing")
        return prefix, cand_ids

    # Throughput notes, measured 2026-10-29 on the vllm-ascend 0.30 stack. Neither is a defect and
    # neither affects a score, but both cost wall clock and both have surprised a reader already.
    #
    # 1. Rows per second falls with prompt length at an exponent near 1.45, NOT 2. An earlier version
    #    of this note said "about the square of length"; that was wrong, and measurement on the full
    #    run corrected it. Cost per row fits a mixed linear-plus-quadratic model,
    #
    #        row seconds ~= 2.0e-4 * L + 1.8e-7 * L**2            (L = prompt tokens)
    #
    #    which is about 30% quadratic at L=336, 40% at L=711 and 66% at L=2224. The mechanism: with
    #    token-budget batching (size = token_budget // longest) the tokens per batch stay about
    #    constant, so the linear-attention layers and the MLPs cost about the same per token at any
    #    length, while the 6 full-attention layers are quadratic and so grow linearly in cost per
    #    batch. Only that last part is quadratic, which is why the exponent sits between 1 and 2.
    #    Measured rows/s/chip on the full run: 11.4 at L=336 (typed-decisions), 4.0 at L=711
    #    (openjev-synth), 0.75 at L=2224 (akhilaaa3) -- ratios of 2.85x and 5.3x, against the 4.5x
    #    and 9.8x a squared law predicts. The model predicts 4.3 rows/s for openjev-synth against 4.0
    #    measured. Expected behaviour for a hybrid architecture under this batching rule, not a bug.
    #
    #    For a runtime estimate, use the fitted model PER SOURCE weighted by that source's share of
    #    the work. A single pooled rate is wrong in both directions: a sample weighted toward short
    #    prompts flatters it, and counting rows rather than work overstates what is left, because the
    #    empty-input and question-only scorers have much shorter prompts and the constant and uniform
    #    classifiers cost essentially nothing.
    #
    # 2. The prefix is recomputed once PER CANDIDATE. Each item expands to one row per level, and
    #    every row re-runs the whole prompt even though the rows share a byte-identical prefix and
    #    differ only in the identifier tokens appended at the end. That is a 2x to 5x waste depending
    #    on the level count. Most identifiers are a single token, so one forward pass over the prefix
    #    would yield every candidate's log-probability at the final position, giving identical
    #    numbers from the same logits.
    #
    #    If anyone implements that: it is an optimization of the PRIMARY evidence path, so it must be
    #    proved score-for-score identical to this implementation on a fixed sample before it replaces
    #    it, not merely faster. Multi-token identifiers need the shared prefix's KV cache reused
    #    rather than the single-position shortcut, so handle them explicitly instead of assuming one
    #    token. Do not change a baseline already scored; re-score instead and compare.

    def score(self, items):
        import torch

        self._load()
        rows = []  # (item index, level index, token ids, n candidate tokens)
        for i, it in enumerate(items):
            prefix, cand_ids = self._encode(it)
            for j, c in enumerate(cand_ids):
                rows.append((i, j, prefix + c, len(c)))
        scores = [[0.0] * len(it["levels"]) for it in items]
        order = sorted(range(len(rows)), key=lambda r: -len(rows[r][2]))
        pad_id = self._tok.pad_token_id if self._tok.pad_token_id is not None else 0

        pos = 0
        while pos < len(order):
            longest = len(rows[order[pos]][2])
            size = max(1, self.token_budget // longest)
            batch = [rows[r] for r in order[pos:pos + size]]
            pos += size
            width = max(len(b[2]) for b in batch)
            keep = max(b[3] for b in batch) + 1
            ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
            mask = torch.zeros((len(batch), width), dtype=torch.long)
            for r, b in enumerate(batch):  # left padding: identifier tokens end every row
                ids[r, width - len(b[2]):] = torch.tensor(b[2])
                mask[r, width - len(b[2]):] = 1
            ids, mask = ids.to(self.device), mask.to(self.device)
            with torch.no_grad():
                try:
                    logits = self._model(input_ids=ids, attention_mask=mask, use_cache=False,
                                         logits_to_keep=keep).logits
                except TypeError:  # model without logits_to_keep: compute all, then slice
                    logits = self._model(input_ids=ids, attention_mask=mask, use_cache=False).logits
                logits = logits[:, -keep:, :].float()
                logp = torch.log_softmax(logits, dim=-1)
            for r, (i, j, toks, n) in enumerate(batch):
                # kept index t predicts token at padded position (width - keep + t + 1)
                total = 0.0
                for q in range(n):
                    t = keep - 1 - n + q          # logits that predict candidate token q
                    total += float(logp[r, t, toks[len(toks) - n + q]])
                scores[i][j] = total
        return [softmax(s) for s in scores]

    def describe(self):
        return {"scorer": self.name, "model_path": self.model_path, "device": self.device,
                "dtype": self.dtype, "render": self.render, "token_budget": self.token_budget}
