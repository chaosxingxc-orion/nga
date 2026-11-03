package spike;

import com.fasterxml.jackson.databind.JsonNode;
import com.networknt.schema.Error;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Schema-level checker — the {@code check(doc) -> errors[]} half of the
 * consumption contract for the three standalone-document families
 * (adoption / judgment / release) and the schema phase of the ledger checker.
 *
 * <p>Wheel discipline: validation rides networknt/json-schema-validator
 * (Draft 2020-12), not a hand-rolled validator. Ecosystem note (machine-verified
 * by this spike): the networknt 2.x/3.x line replaced the 1.x
 * JsonSchemaFactory API — 2.0.0 is the new API on Jackson 2, 3.0.6 the same
 * API on Jackson 3; the 1.x line keeps the factory API most existing material
 * documents. A real consumer must pin the line explicitly.</p>
 *
 * <p>Path normalization: networknt reports instance locations as JSON-Pointer
 * style paths, while the fixture corpus pins wrong-reason substrings against
 * the Python oracle's slash-joined absolute path format — e.g. the judgment
 * pin {@code examples/0/kind} must survive the adapter. The normalization is
 * itself a format-contract finding (the format doc specifies *that* pins
 * match, but not the path-reporting convention a consumer must emit).</p>
 */
public final class SchemaChecker {

    /** Compiled schema handle (schemas are immutable per run). */
    private final Schema schema;

    /** @param schemaPath path to the *.schema.json to validate against */
    public SchemaChecker(Path schemaPath) throws Exception {
        SchemaRegistry registry =
                SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12);
        this.schema = registry.getSchema(Files.readString(schemaPath));
    }

    /**
     * Validate a document, returning errors in the corpus's path convention.
     *
     * @param doc stripped fixture document
     * @return error lines, empty when the document conforms
     */
    public List<String> check(JsonNode doc) {
        List<String> out = new ArrayList<>();
        for (Error e : schema.validate(doc)) {
            String path = normalizePath(e.getInstanceLocation().toString());
            out.add(path + ": " + e.getMessage());
        }
        return out;
    }

    /**
     * JSON-Pointer style location -> the Python oracle's
     * '/'.join(absolute_path) convention that the pins are pinned to.
     */
    static String normalizePath(String instanceLocation) {
        String p = instanceLocation;
        if (p.startsWith("$")) {
            p = p.substring(1);
        }
        if (p.startsWith("/")) {
            p = p.substring(1);
        }
        return p.isEmpty() ? "<root>" : p;
    }
}
