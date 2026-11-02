package spike;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Ledger checker — JSON Schema phase plus the eight cross-event rule families
 * JSON Schema cannot express, mirroring schema/ledger.py (the Python oracle)
 * family by family. These rules are governance semantics (the six-piece
 * domain), i.e. the legal self-build zone; the generic machinery (parsing,
 * schema evaluation, regex) all rides industry libraries.
 *
 * <p>Wrong-reason alignment: rule messages carry the corpus's guard phrases
 * ({@code strictly increasing}, {@code int64}, {@code float syntax},
 * {@code bypass write}, {@code transition}, {@code second adopted}, ...).
 * Which of those phrases are language-neutral field tokens vs English prose
 * pinned to the reference implementations' wording is quantified by
 * {@code PinAudit} in the report — that split is the spike's central
 * contract-gap finding, so the coupling is deliberately kept visible here
 * rather than hidden behind a mapping layer.</p>
 */
public final class LedgerChecker {

    private static final Set<String> ADOPT_STATUSES = Set.of("adopted", "reused", "conflict");
    private static final Set<String> EFFECT_STATUSES =
            Set.of("dispatched", "unresolved", "completed", "failed");
    private static final BigInteger INT64_MAX =
            BigInteger.valueOf(9_223_203_685_477_5807L);
    /** 2^53 as BigInteger — the exact-representation domain boundary. */
    private static final BigInteger TWO_POW_53 =
            BigInteger.valueOf(9_007_199_254_740_992L);

    private final SchemaChecker schemaPhase;

    /** @param schemaPath path to event-ledger.schema.json */
    public LedgerChecker(java.nio.file.Path schemaPath) throws Exception {
        this.schemaPhase = new SchemaChecker(schemaPath);
    }

    /**
     * Full check: schema first (short-circuit, as the Python oracle does),
     * then the eight cross-event families.
     *
     * @param doc stripped ledger document
     * @return error lines, empty when the document conforms
     */
    public List<String> check(JsonNode doc) {
        List<String> errs = schemaPhase.check(doc);
        if (!errs.isEmpty()) {
            return errs;
        }
        List<ObjectNode> events = new ArrayList<>();
        for (JsonNode e : doc.path("events")) {
            events.add((ObjectNode) e);
        }
        ruleMonotonicSeq(events, errs);
        ruleDigestPerOperation(events, errs);
        ruleFloatSyntax(events, errs);
        ruleStatusFamilies(events, errs);
        ruleGrantPinRidesAdopted(events, errs);
        ruleTransitionDag(events, errs);
        ruleIdempotencyPresence(events, errs);
        ruleKeyCoupling(events, errs);
        ruleAttribution(events, errs);
        ruleSingleWriterGrammar(events, errs);
        return errs;
    }

    // -- family 1+2: strictly increasing arbitration_seq, int64 domain ------

    private void ruleMonotonicSeq(List<ObjectNode> events, List<String> errs) {
        List<BigInteger> seqs = new ArrayList<>();
        for (ObjectNode e : events) {
            seqs.add(exactSeq(e.path("arbitration_seq")));
        }
        for (int i = 0; i + 1 < seqs.size(); i++) {
            if (seqs.get(i).compareTo(seqs.get(i + 1)) >= 0) {
                errs.add("[LEDGER.SEQ_NOT_INCREASING] events: arbitration_seq must be strictly increasing, got " + seqs
                        + " — the machine never repeats or rewinds an arbitration sequence");
                break;
            }
        }
        for (BigInteger s : seqs) {
            if (s.compareTo(INT64_MAX) > 0) {
                errs.add("[LEDGER.SEQ_INT64_OVERFLOW] events: arbitration_seq exceeds the int64 domain — the machine's "
                        + "counter domain; such a document is not machine-writable");
                break;
            }
        }
    }

    // -- family 3: one payload digest per operation id ----------------------

    private void ruleDigestPerOperation(List<ObjectNode> events, List<String> errs) {
        Map<String, String> seen = new HashMap<>();
        for (ObjectNode e : events) {
            JsonNode idem = e.path("idempotency");
            if (!idem.isObject()) {
                continue;
            }
            String op = idem.path("operation_id").asText();
            String dig = idem.path("payload_digest").asText();
            String prev = seen.put(op, dig);
            if (prev != null && !prev.equals(dig)) {
                errs.add("[LEDGER.DIGEST_CHANGED_UNDER_KEY] events: operation_id '" + op + "' carries payload_digest '" + dig
                        + "' but an earlier event recorded '" + prev
                        + "' — changed payload under the same key");
            }
        }
    }

    // -- family 4: float syntax beyond ±2^53 has no parser-independent value -
    // RULE DOMAIN NOTE (spike finding): both reference oracles decide this rule
    // in the float64 domain — Go evaluates n.Float64() (the json.Number text
    // parsed through float64, so 9007199254740993.0 folds to exactly 2^53 and
    // is NOT "beyond"), Python evaluates the parsed double likewise. A Java
    // consumer that instead compares the EXACT decimal value (BigDecimal)
    // diverges on odd float twins: 9007199254740993.0 would be rejected. The
    // comparison below therefore mirrors the float64 decision domain, while
    // the message prints whatever the decode arm preserved (folded double or
    // exact decimal — a message-value face difference, not a verdict one).

    private void ruleFloatSyntax(List<ObjectNode> events, List<String> errs) {
        // R16 数值域章程 v2 (user ruling 2026-11-02): this package does no
        // float math — integer LITERALS are the only writable seq form. The
        // v1 ±2^53 sub-domain rule retired with the charter (JCS governs the
        // signature payload only, never the counter).
        for (int i = 0; i < events.size(); i++) {
            JsonNode seq = events.get(i).path("arbitration_seq");
            if (!seq.isFloatingPointNumber()) {
                continue;
            }
            errs.add("[LEDGER.SEQ_FLOAT_SYNTAX] events/" + i + ": arbitration_seq " + seq + " is not an integer literal — "
                    + "the counter domain is machine-written int64; this package does no "
                    + "float math (user ruling 2026-11-02)");
        }
    }

    // -- family 5: status families never cross the event-type boundary ------

    private void ruleStatusFamilies(List<ObjectNode> events, List<String> errs) {
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String type = e.path("event_type").asText();
            String status = e.path("outcome").path("status").asText("");
            boolean ok = "effect".equals(type)
                    ? EFFECT_STATUSES.contains(status)
                    : ADOPT_STATUSES.contains(status);
            if (!ok) {
                String family = ADOPT_STATUSES.contains(status) ? "adoption" : "effect";
                errs.add("[LEDGER.STATUS_FAMILY] events/" + i + ": " + type + " event carries the " + family
                        + "-family status '" + status + "' — the status vocabulary never "
                        + "crosses the event-type boundary");
            }
        }
    }

    // -- family 6: the grant pin rides the adopted event only ---------------

    private void ruleGrantPinRidesAdopted(List<ObjectNode> events, List<String> errs) {
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String type = e.path("event_type").asText();
            String status = e.path("outcome").path("status").asText("");
            boolean granted = e.has("grants_at_decision");
            if (("effect".equals(type) || !"adopted".equals(status)) && granted) {
                errs.add("[LEDGER.GRANTS_ON_NON_ADOPTED] events/" + i + ": " + type + " event (status '" + status
                        + "') carries grants_at_decision — the grant pin rides the adopted "
                        + "event only (stamped once, at the decision point)");
            }
        }
    }

    // -- family 7: per-operation transition order mirrors the machine DAG ---

    private void ruleTransitionDag(List<ObjectNode> events, List<String> errs) {
        Map<String, String> state = new HashMap<>();
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String op = e.path("identity").path("operation_id").asText();
            if (!"adoption".equals(e.path("event_type").asText())) {
                String status = e.path("outcome").path("status").asText();
                String from = state.getOrDefault(op, "");
                switch (status) {
                    case "dispatched" -> {
                        if (!"adopted".equals(from)) {
                            errs.add(notATransition(i, op, status, from));
                        }
                        state.put(op, "dispatched");
                    }
                    case "unresolved" -> {
                        if (!"adopted".equals(from) && !"dispatched".equals(from)) {
                            errs.add(notATransition(i, op, status, from));
                        }
                        state.put(op, "unresolved");
                    }
                    case "completed", "failed" -> {
                        if (!"dispatched".equals(from) && !"unresolved".equals(from)) {
                            errs.add(notATransition(i, op, status, from));
                        }
                        state.put(op, status);
                    }
                    default -> { /* unreachable: schema constrained */ }
                }
                continue;
            }
            if ("adopted".equals(e.path("outcome").path("status").asText())) {
                state.put(op, "adopted");
            }
        }
    }

    private static String notATransition(int i, String op, String status, String from) {
        return "[LEDGER.ILLEGAL_TRANSITION] events/" + i + ": operation '" + op + "': status '" + status + "' after '"
                + (from.isEmpty() ? "nothing" : from) + "' is not a legal state-machine "
                + "transition — a bypass write into the ledger, not a machine transition";
    }

    // -- family 8: idempotency presence, bidirectional ----------------------

    private void ruleIdempotencyPresence(List<ObjectNode> events, List<String> errs) {
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String type = e.path("event_type").asText();
            String status = e.path("outcome").path("status").asText("");
            boolean hasIdem = e.has("idempotency");
            if ("adoption".equals(type) && "conflict".equals(status) && hasIdem) {
                errs.add("[LEDGER.CONFLICT_IDEM_FORBIDDEN] events/" + i + ": conflict event carries idempotency — the loser's "
                        + "digest never enters the registry; carrying it is a bypass write, "
                        + "not a machine transition");
            }
            boolean needsIdem = "effect".equals(type)
                    || "adopted".equals(status) || "reused".equals(status);
            if (needsIdem && !hasIdem) {
                errs.add("[LEDGER.IDEM_REQUIRED] events/" + i + ": " + type + " event (status '" + status
                        + "') must carry idempotency — the machine writes it on every "
                        + "non-conflict event; its absence is a bypass write, not a machine "
                        + "transition");
            }
        }
    }

    // -- family 9: idempotency.operation_id == identity.operation_id --------

    private void ruleKeyCoupling(List<ObjectNode> events, List<String> errs) {
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            JsonNode idem = e.path("idempotency");
            if (idem.isObject() && !idem.path("operation_id").asText()
                    .equals(e.path("identity").path("operation_id").asText())) {
                errs.add("[LEDGER.IDEM_IDENTITY_MISMATCH] events/" + i + ": idempotency.operation_id '"
                        + idem.path("operation_id").asText() + "' does not match "
                        + "identity.operation_id '" + e.path("identity").path("operation_id").asText()
                        + "' — the machine writes them equal; a mismatch is a bypass write, "
                        + "not a machine transition");
            }
        }
    }

    // -- family 10: effect attribution == the adopted pin --------------------

    private void ruleAttribution(List<ObjectNode> events, List<String> errs) {
        Map<String, String> pins = new HashMap<>();
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String op = e.path("identity").path("operation_id").asText();
            String type = e.path("event_type").asText();
            if ("adoption".equals(type) && "adopted".equals(
                    e.path("outcome").path("status").asText())) {
                pins.put(op, attributionKey(e));
            } else if ("effect".equals(type) && pins.containsKey(op)) {
                if (!attributionKey(e).equals(pins.get(op))) {
                    errs.add("[LEDGER.ATTRIBUTION_DIVERGENCE] events/" + i + ": effect event's attribution (identity/versions/"
                            + "accountability) differs from the adopted pin for operation '"
                            + op + "' — the machine stamps the winner's pin on every effect "
                            + "event; a divergence is a bypass write, not a machine transition");
                }
            }
        }
    }

    private static String attributionKey(ObjectNode e) {
        return e.path("identity").toString() + "\u0000" + e.path("versions").toString()
                + "\u0000" + e.path("accountability").toString();
    }

    // -- family 11: single-writer event-sequence grammar ---------------------

    private void ruleSingleWriterGrammar(List<ObjectNode> events, List<String> errs) {
        Set<String> adopted = new HashSet<>();
        for (int i = 0; i < events.size(); i++) {
            ObjectNode e = events.get(i);
            String op = e.path("identity").path("operation_id").asText();
            String type = e.path("event_type").asText();
            if ("adoption".equals(type)) {
                if ("adopted".equals(e.path("outcome").path("status").asText())) {
                    if (!adopted.add(op)) {
                        errs.add("[LEDGER.DOUBLE_ADOPTED] events/" + i + ": operation '" + op + "' already has an "
                                + "adopted event — a second adopted event would re-pin the "
                                + "machine's state mid-flight (a bypass write, not a machine "
                                + "transition)");
                    }
                } else if (!adopted.contains(op)) {
                    errs.add("[LEDGER.EVENT_BEFORE_ADOPTION] events/" + i + ": " + type + " event for operation '" + op
                            + "' precedes its adopted event — a bypass write into the ledger, "
                            + "not a machine transition");
                }
            } else if (!adopted.contains(op)) {
                errs.add("[LEDGER.EVENT_BEFORE_ADOPTION] events/" + i + ": effect event for operation '" + op
                        + "' precedes its adopted event — a bypass write into the ledger, "
                        + "not a machine transition");
            }
        }
    }

    // -- exact seq view -------------------------------------------------------

    /**
     * Exact-decoded arbitration_seq: integral-syntax numbers are exact at any
     * magnitude (BigInteger under the hood); integral float-syntax values are
     * recovered exactly via decimalValue(). This is the UseNumber equivalent.
     */
    static BigInteger exactSeq(JsonNode node) {
        if (node.isIntegralNumber()) {
            return node.bigIntegerValue();
        }
        return node.decimalValue().toBigIntegerExact();
    }
}
