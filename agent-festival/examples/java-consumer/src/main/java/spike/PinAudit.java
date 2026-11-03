package spike;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Pin classification — the wrong-reason language-neutrality audit.
 *
 * <p>Every invalid fixture's {@code _expect_match} is classified as a
 * FIELD token (a JSON field name / schema path segment / enum value —
 * language-neutral: any implementation that reports the offending location
 * or value naturally contains it) or a PROSE phrase (English wording pinned
 * to the reference implementations' hand-written rule messages — a foreign
 * consumer hits it only by copying the phrase or installing a guard-phrase
 * mapping layer). The split is declared per-pin with the classification
 * rationale so the audit is reviewable rather than heuristic.</p>
 */
public final class PinAudit {

    /** Pins that are English prose from the reference checkers' messages. */
    private static final Map<String, Set<String>> PROSE = Map.of(
            "ledger", Set.of(
                    "must carry idempotency",   // idem-presence rule wording
                    "does not match",           // key-coupling rule wording
                    "increasing",               // monotonicity rule wording
                    "float syntax",             // float-syntax rule wording
                    "int64",                    // domain rule wording
                    "bypass",                   // bypass-write rule wording
                    "transition",               // transition-DAG rule wording
                    "second adopted",           // double-adopted rule wording
                    "conflict event carries idempotency", // conflict-idem rule wording
                    "effect-family",            // status-family rule wording
                    "attribution"               // attribution rule wording
            ));

    /**
     * Classify a pin.
     *
     * @param family suite label
     * @param pin the _expect_match substring
     * @return "FIELD" or "PROSE"
     */
    public static String classify(String family, String pin) {
        return PROSE.getOrDefault(family, Set.of()).contains(pin) ? "PROSE" : "FIELD";
    }

    /** Summary line over the audit rows. */
    public static String summarize(List<SuiteRunner.PinRow> rows) {
        long field = rows.stream().filter(r -> "FIELD".equals(r.pinKind())).count();
        long prose = rows.stream().filter(r -> "PROSE".equals(r.pinKind())).count();
        long none = rows.stream().filter(r -> "NONE".equals(r.pinKind())).count();
        long missed = rows.stream().filter(r -> !r.hit()).count();
        return ("pins: %d total, %d FIELD (neutral), %d PROSE (phrasing-coupled), "
                + "%d unpinned; wrong-reason misses: %d")
                .formatted(rows.size(), field, prose, none, missed);
    }

    private PinAudit() { }
}
