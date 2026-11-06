"""Frozen train / held-out splits (pre-registration section 2.1).

* ``group70``: 70 / 30 by SHA-256 of ``group_id``. All variants of a group land on the same side.
* ``question70``: akhilaaa3 only. 70 / 30 by SHA-256 of ``qname``, so no question appears on both
  sides. Not meaningful for openjev-synth (one qname) and near-meaningless for typed-decisions (15).

The bucket is the first 8 bytes of the digest as a big-endian integer modulo 10000; a key is train
when its bucket is below 7000. The result does not depend on file order, platform or run.
"""
import hashlib

TRAIN, HELDOUT = "train", "heldout"
_BUCKETS = 10000
_TRAIN_BUCKETS = 7000


def bucket(key):
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % _BUCKETS


class Splitter:
    """Maps a record (or readout row) to ``train`` or ``heldout`` by hashing one field."""

    def __init__(self, name, field):
        self.name = name
        self.field = field

    def assign(self, row):
        return TRAIN if bucket(row[self.field]) < _TRAIN_BUCKETS else HELDOUT


GROUP70 = Splitter("group70", "group_id")
QUESTION70 = Splitter("question70", "qname")
SPLITTERS = {s.name: s for s in (GROUP70, QUESTION70)}

# Which splits are reported for which record source (pre-reg 2.1: question-disjoint only for akhilaaa3).
def splitters_for_source(source):
    if source.startswith("akhilaaa3"):
        return (GROUP70, QUESTION70)
    return (GROUP70,)


class TrainView:
    """Rows of the train side of one split, and nothing else.

    The only way to obtain one is ``TrainView.of``, which filters by the splitter. Everything that
    fits a parameter (thresholds.fit_thresholds, ConstantClassifierScorer.fit) accepts a TrainView
    and nothing else, so a fit on held-out rows cannot be expressed through the public API.
    """

    __slots__ = ("splitter", "rows")
    _token = object()

    def __init__(self, splitter, rows, token):
        if token is not TrainView._token:
            raise TypeError("build a TrainView with TrainView.of(rows, splitter)")
        self.splitter = splitter
        self.rows = tuple(rows)

    @classmethod
    def of(cls, rows, splitter):
        return cls(splitter, [r for r in rows if splitter.assign(r) == TRAIN], cls._token)

    def __len__(self):
        return len(self.rows)
