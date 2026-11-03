package spike;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Iterator;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Fixture loader — the {@code load(fixturePath)} half of the cross-language
 * consumption contract defined in docs/conformance-fixture-format.md §4.
 *
 * <p>Contract semantics implemented (mirrors schema/_suite.py and the V28/V32
 * hardening): a parse failure yields {@code doc=null} plus a parse error whose
 * text the wrong-reason pin must still be matchable against (the pin is
 * best-effort extracted from the raw bytes); a wrong-typed {@code _expect_match}
 * is a LOUD failure, never a silent downgrade to "no pin" (V28 F-1); every
 * {@code _expect*} key is stripped before the document reaches the checker.</p>
 *
 * <p>Integer-domain discipline (format doc §3): decoding must preserve exact
 * integers — this is the Java equivalent of Go's {@code UseNumber} / Python's
 * native int. Jackson's default node factory already lands integral JSON
 * numbers on IntNode/LongNode/BigIntegerNode (exact at any magnitude, no
 * configuration needed — unlike Go, where the default float64 decode loses
 * the 2^53-adjacent rules silently). Floating-syntax numbers go to DoubleNode
 * by default or DecimalNode under {@code USE_BIG_DECIMAL_FOR_FLOATS} — both
 * arms are exercised by the integer-domain experiment so the equivalence
 * claim is measured, not asserted.</p>
 */
public final class FixtureLoader {

    /** Raw-text pin extraction for the rejected-at-parse path (V32 M-1 twin). */
    private static final Pattern PIN_RE = Pattern.compile("\"_expect_match\"\\s*:\\s*\"([^\"]*)\"");

    private final JsonMapper mapper;

    public enum FloatDomain { DOUBLE, BIG_DECIMAL }

    /**
     * Functional constructor: the float-domain arm is explicit because the
     * experiment matrix needs both. Note: {@code withExactBigDecimals} is
     * deprecated AND has no effect on {@code readTree} — the working switch is
     * {@code USE_BIG_DECIMAL_FOR_FLOATS} (verified by this spike: under it,
     * {@code 9007199254740993.0} parses to the exact DecimalNode 9007199254740993
     * instead of the folded double).
     *
     * @param floatDomain DOUBLE = Jackson default (folded); BIG_DECIMAL = exact
     */
    public FixtureLoader(FloatDomain floatDomain) {
        JsonMapper.Builder builder = JsonMapper.builder();
        if (floatDomain == FloatDomain.BIG_DECIMAL) {
            builder.enable(com.fasterxml.jackson.databind.DeserializationFeature
                    .USE_BIG_DECIMAL_FOR_FLOATS);
        }
        this.mapper = builder.build();
    }

    /** Loaded fixture: document (null on parse failure), pin, load error. */
    public record Loaded(JsonNode doc, String pin, String error) {
        /** True when the JSON itself failed to parse (rejected-at-parse). */
        public boolean rejectedAtParse() {
            return doc == null && error != null && error.startsWith("document rejected at parse");
        }
    }

    /**
     * Load one fixture per the format contract.
     *
     * @param path fixture file
     * @return loaded record; never null
     */
    public Loaded load(Path path) {
        String raw;
        try {
            raw = Files.readString(path);
        } catch (Exception e) {
            return new Loaded(null, null, "document rejected at read: " + e.getMessage());
        }
        JsonNode doc;
        try {
            doc = mapper.readTree(raw);
        } catch (Exception e) {
            Matcher m = PIN_RE.matcher(raw);
            String pin = m.find() ? m.group(1) : null;
            return new Loaded(null, pin, "document rejected at parse: " + e.getMessage());
        }
        if (!doc.isObject()) {
            return new Loaded(null, null,
                    "document rejected at parse: fixture root must be a JSON object");
        }
        // Strip every _expect* key, then enforce the pin's string type.
        var obj = (com.fasterxml.jackson.databind.node.ObjectNode) doc;
        JsonNode pinNode = obj.path("_expect_match");
        String pin = null;
        if (!pinNode.isMissingNode()) {
            if (!pinNode.isTextual()) {
                return new Loaded(doc, null, "_expect_match must be a string, got "
                        + typeName(pinNode));
            }
            pin = pinNode.asText();
        }
        stripExpectKeys(obj);
        return new Loaded(doc, pin, null);
    }

    private static void stripExpectKeys(com.fasterxml.jackson.databind.node.ObjectNode obj) {
        Iterator<String> names = obj.fieldNames();
        java.util.List<String> toRemove = new java.util.ArrayList<>();
        while (names.hasNext()) {
            String name = names.next();
            if (name.startsWith("_expect")) {
                toRemove.add(name);
            }
        }
        for (String name : toRemove) {
            obj.remove(name);
        }
    }

    private static String typeName(JsonNode node) {
        return node.getNodeType().toString().toLowerCase();
    }
}
