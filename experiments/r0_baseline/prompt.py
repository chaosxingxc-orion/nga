"""The one prompt used by the baseline readout and by any later training run.

Pure Python, no model, tokenizer, clock or dict-order dependence: the same record gives a
byte-identical string. Any edit to the layout below MUST change PROMPT_VERSION; the version is
written into every readout header and the report header, and the tests lock the rendered text.
A report with a different version is not comparable (decision line B-4).

Format (recorded for the pre-registration): RAW COMPLETION. The chat template of the model
(chat_template.jinja) is NOT applied; the prompt is plain text ending in the answer cue and the
level identifier is scored as its continuation.

Fixed order (CLAUDE.md section 4): task definition, input, then one branch per candidate level.

Rendering (AMBIGUITY A3).  The pre-registration says levels are "neutral identifiers plus
definitions, with the harness mapping back to business names".  Read literally, that replaces every
name by a positional identifier, which makes the prompt identical across the four T1 name variants:
the T1 flip rate is then 0 by construction, equal to the empty-input baseline, and decision line B-2
can never pass.  Two render modes are therefore provided and the choice is recorded in every
readout header:

* ``record_name`` (default): the identifier shown is the record's ``name`` field.  In T1 this is the
  thing the task varies (digits, letters, random string, original word), so T1 measures name
  sensitivity.  The business name is never shown separately; the harness maps the chosen
  identifier back to the level id.
* ``neutral``: positional identifiers L1, L2, ... independent of the record's names.  Use it to
  verify the rendering fix (R2-1); on T1 it must give flip rate 0 by construction.

Input modes, used by the degenerate baselines (pre-reg section 4):

* ``full``: the record's input as given.
* ``blank``: empty-input baseline.  The "Input:" section stays, its text is empty.
* ``drop``: question-only baseline.  The whole input section is removed.
"""

PROMPT_VERSION = "r0-prompt-v1"
PROMPT_FORMAT = "raw-completion (no chat template)"
RENDER_MODES = ("record_name", "neutral")

from collections import namedtuple

# text: the prompt. labels: identifiers shown, in declared level order. to_original: label -> level id.
# candidates: the strings scored after the prompt (a space plus each label).
Prompt = namedtuple("Prompt", "text labels to_original candidates version")
INPUT_MODES = ("full", "blank", "drop")
ANSWER_CUE = "Answer:"


def level_labels(item, render):
    if render == "record_name":
        return [l["name"] for l in item["levels"]]
    if render == "neutral":
        return [f"L{i + 1}" for i in range(len(item["levels"]))]
    raise ValueError(f"unknown render mode {render!r}")


def input_mode_of(item):
    return item.get("input_mode", "full")


def build_prompt(record, render="record_name", input_mode=None):
    """Render one record. Returns a ``Prompt``; ``Prompt.text`` is the string.

    ``render`` is "record_name" (the record's own level names) or "neutral" (L1, L2, ... by list
    position). The default is "record_name" because that is what the R0 baseline pre-registration
    fixes (see R0-BASELINE-PREREG.md amendment 8.1): T1's four variants differ ONLY in each
    level's name, so neutral rendering makes all four prompts identical and forces the flip rate
    to 0 by construction. Neutral rendering is the mitigation for defect 1 and is measured later
    as a separate intervention arm, not as part of this baseline.
    ``input_mode`` defaults to the record's ``input_mode`` field ("full" when absent).
    """
    item = record
    if item["candidate_set"] != "exclusive":
        raise NotImplementedError("only exclusive candidate sets are scored in R0")
    labels = level_labels(item, render)
    mode = input_mode or input_mode_of(item)
    if mode not in INPUT_MODES:
        raise ValueError(f"unknown input mode {mode!r}")
    parts = [item["task_definition"].strip(), ""]
    if mode != "drop":
        parts += ["Input:", "" if mode == "blank" else item["input"].strip(), ""]
    parts += [f"Question: {item['question'].strip()}", "", "Options:"]
    parts += [f"- {lab}: {lv['definition'].strip()}" for lab, lv in zip(labels, item["levels"])]
    parts += ["", "Answer with the identifier of exactly one option.", ANSWER_CUE]
    to_original = {lab: lv["id"] for lab, lv in zip(labels, item["levels"])}
    return Prompt("\n".join(parts), tuple(labels), tuple((l, to_original[l]) for l in labels),
                  tuple(" " + lab for lab in labels), PROMPT_VERSION)


def blank_input(item):
    return dict(item, input="", input_mode="blank")


def drop_input(item):
    return dict(item, input="", input_mode="drop")
