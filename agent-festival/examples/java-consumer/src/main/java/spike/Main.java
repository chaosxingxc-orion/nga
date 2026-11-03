package spike;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * GEPA R3 spike entry point: a Java consumer of the festival conformance
 * fixtures (ledger / adoption / judgment / release families) plus the three
 * gap-verification experiments (count reconciliation, wrong-reason pin
 * neutrality, integer-domain equivalence).
 *
 * <p>Usage: java spike.Main [path-to-agent-festival/schema]</p>
 */
public final class Main {

    /** Oracle-pinned counts (Python tuple asserts / Go summary lines). */
    private static final Map<String, int[]> ORACLE_PINS = new LinkedHashMap<>();
    /** docs/conformance-fixture-format.md §1 hand-copied counts (the 4th copy). */
    private static final Map<String, int[]> FORMAT_DOC_CLAIMS = new LinkedHashMap<>();

    static {
        ORACLE_PINS.put("ledger", new int[] {10, 26});
        ORACLE_PINS.put("adoption", new int[] {2, 5});
        ORACLE_PINS.put("judgment", new int[] {2, 19});
        ORACLE_PINS.put("release", new int[] {3, 14});
        FORMAT_DOC_CLAIMS.put("ledger", new int[] {10, 26});
        FORMAT_DOC_CLAIMS.put("adoption", new int[] {2, 5});
        FORMAT_DOC_CLAIMS.put("judgment", new int[] {2, 19});
        FORMAT_DOC_CLAIMS.put("release", new int[] {2, 9}); // the PRE-E1 header claim, kept as the stale-detection probe (E1 fixed the doc to 3+14)
    }

    public static void main(String[] args) throws Exception {
        Path schemaDir = args.length > 0
                ? Path.of(args[0])
                : Path.of("../agent-festival/schema").toAbsolutePath().normalize();
        if (!Files.isDirectory(schemaDir)) {
            System.err.println("schema dir not found: " + schemaDir);
            System.exit(2);
        }
        int rc = 0;

        System.out.println("== Part 1: four-family suites, Jackson default (DOUBLE) arm ==");
        LedgerChecker ledger = new LedgerChecker(schemaDir.resolve("event-ledger.schema.json"));
        SchemaChecker adoption =
                new SchemaChecker(schemaDir.resolve("adoption.schema.json"));
        SchemaChecker judgment =
                new SchemaChecker(schemaDir.resolve("judgment.schema.json"));
        SchemaChecker release =
                new SchemaChecker(schemaDir.resolve("release.schema.json"));
        FixtureLoader defaultLoader = new FixtureLoader(FixtureLoader.FloatDomain.DOUBLE);
        SuiteRunner main = new SuiteRunner(defaultLoader);
        Path ex = schemaDir.resolve("examples");
        rc += main.run("ledger", ex.resolve("ledger/valid"), ex.resolve("ledger/invalid"),
                ledger::check, 10, 26, true);
        rc += main.run("adoption", ex.resolve("adoption/valid"), ex.resolve("adoption/invalid"),
                adoption::check, 2, 5, true);
        rc += main.run("judgment", ex.resolve("judgment/valid"), ex.resolve("judgment/invalid"),
                judgment::check, 2, 19, true);
        rc += main.run("release", ex.resolve("release/valid"), ex.resolve("release/invalid"),
                release::check, 3, 14, true);

        System.out.println();
        System.out.println("== Part 1b: same suites under BIG_DECIMAL arm (summary only) ==");
        FixtureLoader decimalLoader = new FixtureLoader(FixtureLoader.FloatDomain.BIG_DECIMAL);
        SuiteRunner decimal = new SuiteRunner(decimalLoader);
        rc += decimal.run("ledger", ex.resolve("ledger/valid"), ex.resolve("ledger/invalid"),
                ledger::check, 10, 26, false);
        rc += decimal.run("adoption", ex.resolve("adoption/valid"),
                ex.resolve("adoption/invalid"), adoption::check, 2, 5, false);
        rc += decimal.run("judgment", ex.resolve("judgment/valid"),
                ex.resolve("judgment/invalid"), judgment::check, 2, 19, false);
        rc += decimal.run("release", ex.resolve("release/valid"),
                ex.resolve("release/invalid"), release::check, 3, 14, false);

        System.out.println();
        System.out.println("== Part 2: wrong-reason pin audit ==");
        System.out.printf("%-10s %-40s %-38s %-6s%n", "FAMILY", "FIXTURE", "PIN", "KIND");
        for (SuiteRunner.PinRow row : main.audit) {
            System.out.printf("%-10s %-40s %-38s %-6s %s%n", row.family(), row.fixture(),
                    row.pin(), row.pinKind(), row.hit() ? "hit" : "MISS");
        }
        System.out.println(PinAudit.summarize(main.audit));

        System.out.println();
        System.out.println("== Part 3: corpus count manifest (machine-generated) vs "
                + "format-doc hand copy ==");
        rc += countManifest(ex);

        System.out.println();
        System.out.println("== Part 4: integer-domain experiment (2^53 / int64 / "
                + "float syntax) ==");
        rc += integerDomainExperiment(ledger);

        System.out.println();
        System.out.println("== Part 5: regex-semantic probe (pattern-face parity) ==");
        rc += regexProbe();

        System.out.println();
        System.out.println("== Part 6: loader hardening self-tests (V28/V32 twins) ==");
        rc += loaderSelfTests();

        System.out.println();
        System.out.println(rc == 0
                ? "SPIKE-GREEN: all suites green under both arms, all experiments as predicted"
                : "SPIKE-RED: " + rc + " failure groups — see above");
        System.exit(rc == 0 ? 0 : 1);
    }

    // ---------------------------------------------------------------------

    private static int countManifest(Path ex) throws Exception {
        int bad = 0;
        System.out.printf("%-28s %12s %15s %18s%n", "dir", "actual", "oracle-pin",
                "format-doc-claim");
        // growth families with valid/invalid splits (envelopes is a base-family
        // dir but has the same split layout; keys is a hybrid: one top-level
        // file plus an invalid/ subdir — both are machine-discovered here,
        // which is the point of a generated manifest)
        List<String> splitDirs = List.of("ledger", "adoption", "judgment", "release",
                "compose", "replay", "evidlog", "envelopes");
        int total = 0;
        for (String fam : splitDirs) {
            int v = countJson(ex.resolve(fam + "/valid"));
            int i = countJson(ex.resolve(fam + "/invalid"));
            total += v + i;
            int[] oracle = ORACLE_PINS.get(fam);
            int[] doc = FORMAT_DOC_CLAIMS.get(fam);
            String oracleCell = oracle == null ? "-" : oracle[0] + "+" + oracle[1];
            String docCell = doc == null ? "-" : doc[0] + "+" + doc[1]
                    + (oracle != null && (doc[0] != oracle[0] || doc[1] != oracle[1])
                    ? " STALE" : "");
            System.out.printf("%-28s %9d+%d %15s %18s%n", fam, v, i, oracleCell, docCell);
        }
        int keysTop = countJson(ex.resolve("keys"));
        int keysInvalid = countJson(ex.resolve("keys/invalid"));
        total += keysTop + keysInvalid;
        System.out.printf("%-28s %12s %15s %18s%n", "keys (hybrid: 1 file + invalid/)",
                keysTop + "+" + keysInvalid, "4 (README)", "-");
        for (String d : List.of("valid", "invalid")) {
            int n = countJson(ex.resolve(d));
            total += n;
            System.out.printf("%-28s %12d %15s %18s%n", d, n, "-", "-");
        }
        System.out.println("total actual = " + total
                + "   (format-doc machine manifest now carries the live counts; the 2+9 probe column above is the pre-E1 historical claim kept deliberately to prove this detector can see staleness — E1 already healed the doc)");
        if (total != 200) {
            System.out.println("COUNT-FAIL: total drifted from the 200 pinned by this spike");
            bad++;
        }
        return bad;
    }

    private static int countJson(Path dir) {
        try (var s = Files.list(dir)) {
            return (int) s.filter(p -> p.toString().endsWith(".json")).count();
        } catch (Exception e) {
            return -1;
        }
    }

    // ---------------------------------------------------------------------

    /** Minimal otherwise-conforming two-event ledger doc with raw seq literals. */
    private static String twoEventDoc(String rawSeqA, String rawSeqB) {
        return """
                {
                  "ledger_version": "0.1.0",
                  "events": [
                    {
                      "event_type": "adoption",
                      "arbitration_seq": %s,
                      "identity": {"business_request_id": "br-x", "operation_id": "op-x"},
                      "versions": {"evidence": "ev-1", "rule": "r-1", "model": "m-1",
                                   "readout": "ro-1", "policy": "p-1"},
                      "outcome": {"status": "adopted", "detail": "t"},
                      "idempotency": {"operation_id": "op-x",
                        "payload_digest": "sha256:%s"},
                      "grants_at_decision": [{"kind": "data", "selector": "s://x",
                        "actions": ["read"], "effect": "none"}]
                    },
                    {
                      "event_type": "effect",
                      "arbitration_seq": %s,
                      "identity": {"business_request_id": "br-x", "operation_id": "op-x"},
                      "versions": {"evidence": "ev-1", "rule": "r-1", "model": "m-1",
                                   "readout": "ro-1", "policy": "p-1"},
                      "outcome": {"status": "dispatched", "detail": "t"},
                      "idempotency": {"operation_id": "op-x",
                        "payload_digest": "sha256:%s"}
                    }
                  ]
                }
                """.formatted(rawSeqA, hex64(), rawSeqB, hex64());
    }

    private static String hex64() {
        return "a".repeat(64);
    }

    private static int integerDomainExperiment(LedgerChecker ledger) throws Exception {
        record Case(String name, String doc, String expected, String pin) { }
        // expectations pinned to the REFERENCE oracles' behavior (Python
        // verified empirically; Go rule code reads n.Float64(), i.e. the same
        // float64 decision domain)
        List<Case> cases = List.of(
                new Case("adjacent-2e53-increasing (2^53, 2^53+1) int syntax",
                        twoEventDoc("9007199254740992", "9007199254740993"), "ACCEPT", null),
                new Case("adjacent-2e53-decreasing (2^53+1, 2^53) int syntax",
                        twoEventDoc("9007199254740993", "9007199254740992"), "REJECT",
                        "increasing"),
                new Case("float-syntax-beyond-2e53 (9007199254740994.0)",
                        twoEventDoc("9007199254740994.0", "9007199254740995"), "REJECT",
                        "float syntax"),
                new Case("float-syntax-integral-small (0.0, 1.0) — valid twin",
                        twoEventDoc("0.0", "1.0"), "ACCEPT", null),
                new Case("int64-overflow (2^63)",
                        twoEventDoc("9223372036854775808", "9223372036854775809"), "REJECT",
                        "int64"),
                // odd twin: parses (float64) to exactly 2^53 — NOT beyond — so
                // both reference oracles ACCEPT it (empirically verified on the
                // Python oracle; Go decides through Float64 likewise)
                new Case("odd-float-twin (9007199254740993.0) folds to 2^53 -> legal",
                        twoEventDoc("9007199254740993.0", "9007199254740994"), "ACCEPT",
                        null));
        int bad = 0;
        for (FixtureLoader.FloatDomain arm : FixtureLoader.FloatDomain.values()) {
            System.out.println("-- arm: " + arm);
            FixtureLoader loader = new FixtureLoader(arm);
            for (Case c : cases) {
                JsonNode doc = loader.load(writeTemp(c.doc())).doc();
                List<String> errs = ledger.check(doc);
                String verdict = errs.isEmpty() ? "ACCEPT" : "REJECT";
                boolean verdictOk = verdict.equals(c.expected);
                boolean pinOk = c.pin() == null
                        || errs.stream().anyMatch(e -> e.contains(c.pin()));
                if (!verdictOk || !pinOk) {
                    bad++;
                }
                System.out.printf("   %-62s -> %-7s verdict:%-3s pin:%-3s %s%n",
                        c.name(), verdict, verdictOk ? "ok" : "BAD", pinOk ? "ok" : "BAD",
                        errs.isEmpty() ? "" : firstShort(errs));
            }
        }
        // fold simulation: what a double-domain (naive) seq consumer would see
        FixtureLoader loader = new FixtureLoader(FixtureLoader.FloatDomain.DOUBLE);
        JsonNode doc = loader.load(writeTemp(twoEventDoc("9007199254740992",
                "9007199254740993"))).doc();
        double s0 = doc.path("events").get(0).path("arbitration_seq").asDouble();
        double s1 = doc.path("events").get(1).path("arbitration_seq").asDouble();
        System.out.printf("   fold-simulation: seq.doubleValue() gives %.1f and %.1f -> "
                        + "strictly-increasing=%s (a double-domain MONOTONICITY consumer %s "
                        + "the legal adjacent pair)%n",
                s0, s1, s0 < s1, s0 < s1 ? "accepts" : "FALSELY REJECTS");
        if (s0 < s1) {
            bad++; // the whole point: double folding must NOT preserve order here
        }
        // arm-divergence counterfactual on the odd twin: under exact-decimal
        // decoding the VALUE is 9007199254740993 (> 2^53) — a rule that
        // compared exact decimals would flip this verdict away from both
        // reference oracles; this spike's rule deliberately stays float64.
        for (FixtureLoader.FloatDomain arm : FixtureLoader.FloatDomain.values()) {
            FixtureLoader l = new FixtureLoader(arm);
            JsonNode d = l.load(writeTemp(twoEventDoc("9007199254740993.0",
                    "9007199254740994"))).doc();
            JsonNode seq = d.path("events").get(0).path("arbitration_seq");
            System.out.printf("   odd twin under %-11s: value=%-20s exact-beyond-2^53=%s "
                            + "(verdict stays ACCEPT: rule domain is float64, matching both "
                            + "oracles)%n",
                    arm, seq.decimalValue().toBigInteger().toString(),
                    seq.decimalValue().toBigInteger()
                            .compareTo(java.math.BigInteger.valueOf(9007199254740992L)) > 0);
        }
        return bad;
    }

    private static String firstShort(List<String> errs) {
        String s = errs.get(0);
        return s.length() > 110 ? s.substring(0, 110) + "..." : s;
    }

    private static Path writeTemp(String content) throws Exception {
        Path p = Files.createTempFile("spike-case", ".json");
        Files.writeString(p, content);
        return p;
    }

    // ---------------------------------------------------------------------

    private static int regexProbe() throws Exception {
        int bad = 0;
        Pattern p = Pattern.compile("^sha256:[0-9a-f]{64}$");
        String hex = "b".repeat(64);
        boolean plain = p.matcher("sha256:" + hex).find();
        boolean trailingNewline = p.matcher("sha256:" + hex + "\n").find();
        boolean middleNewline = p.matcher("sha256:" + hex + "\nx").find();
        System.out.printf("   java.util.regex find-mode: plain=%s trailing-\\n=%s middle-\\n=%s"
                        + "%n   (python re.search reference, empirically verified: "
                        + "plain=ACCEPT trailing-\\n=ACCEPT middle-\\n=REJECT — identical)%n",
                plain, trailingNewline, middleNewline);
        if (!plain || !trailingNewline || middleNewline) {
            bad++;
        }
        // through networknt (the schema face a Java consumer actually runs)
        String schemaText = "{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\","
                + "\"type\":\"string\",\"pattern\":\"^sha256:[0-9a-f]{64}$\"}";
        var registry = com.networknt.schema.SchemaRegistry
                .withDefaultDialect(com.networknt.schema.SpecificationVersion.DRAFT_2020_12);
        var schema = registry.getSchema(schemaText);
        boolean vPlain = schema.validate(com.fasterxml.jackson.databind.node.TextNode
                .valueOf("sha256:" + hex)).isEmpty();
        boolean vFold = schema.validate(com.fasterxml.jackson.databind.node.TextNode
                .valueOf("sha256:" + hex + "\n")).isEmpty();
        if (!vPlain) {
            bad++;
        }
        if (vFold) {
            System.out.println("   networknt matches java.util.regex find-mode: ok");
        } else {
            System.out.println("   FINDING (pattern-face divergence): networknt 2.0.0 "
                    + "REJECTS a digest with a trailing \\n that Python re.search and "
                    + "java.util.regex find() both accept (networknt matches in full-match "
                    + "mode). Same schema, same input, verdict forks across implementations "
                    + "— and the corpus has no fixture pinning this edge.");
        }
        return bad;
    }

    // ---------------------------------------------------------------------

    private static int loaderSelfTests() {
        int bad = 0;
        FixtureLoader loader = new FixtureLoader(FixtureLoader.FloatDomain.DOUBLE);
        try {
            // wrong-typed pin must be LOUD (V28 F-1)
            Path wrongTyped = writeTemp("{\"poison\": \"x\", \"_expect_match\": 5}");
            FixtureLoader.Loaded l1 = loader.load(wrongTyped);
            boolean loud = l1.error() != null
                    && l1.error().contains("_expect_match must be a string");
            System.out.println("   wrong-typed pin fails LOUD: " + (loud ? "ok" : "BAD"));
            if (!loud) {
                bad++;
            }
            // parse failure keeps the pin armed against the parse error (V32 M-1)
            // (this JSON is genuinely unterminated — no closing brace)
            Path unparseable = writeTemp("{\"poison\": \"unterminated\", "
                    + "\"_expect_match\": \"zzz\"");
            FixtureLoader.Loaded l2 = loader.load(unparseable);
            boolean armed = l2.doc() == null && "zzz".equals(l2.pin())
                    && l2.error() != null && l2.error().contains("rejected at parse");
            System.out.println("   parse-failed fixture keeps pin armed: " + (armed ? "ok"
                    : "BAD") + " (doc=null:" + (l2.doc() == null)
                    + ", pin=zzz:" + "zzz".equals(l2.pin()) + ")");
            if (!armed) {
                bad++;
            }
        } catch (Exception e) {
            System.out.println("   self-test exception: " + e);
            bad++;
        }
        return bad;
    }

    private Main() { }
}
