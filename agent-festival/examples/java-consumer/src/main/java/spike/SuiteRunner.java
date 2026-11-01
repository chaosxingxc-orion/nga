package spike;

import com.fasterxml.jackson.databind.JsonNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.function.Function;

/**
 * Suite runner — the {@code suite(dirs, check)} half of the consumption
 * contract, mirroring schema/_suite.py line for line in behavior: two-phase
 * (must-accept / must-reject), wrong-reason pin check against any error line,
 * loud failure on unreadable pins, rejected-at-parse fixtures keep their pin
 * armed against the parse error, and the D93 corpus-count floor.
 *
 * <p>Count floors here are pinned from the ORACLE sources (the Python tuple
 * asserts / Go test summary lines), deliberately NOT from
 * docs/conformance-fixture-format.md §1 — whose release row and corpus total
 * are measurably stale (the spike's count-reconciliation experiment quantifies
 * the drift). A consumer that trusted the format doc's table would fail its
 * own count floor: that is the fourth-copy problem in action.</p>
 */
public final class SuiteRunner {

    /** Checker interface: errors for a stripped document, empty = conforms. */
    public interface Checker extends Function<JsonNode, List<String>> { }

    /** One row of the wrong-reason audit (per invalid fixture). */
    public record PinRow(String family, String fixture, String pin, String pinKind,
                         boolean hit, String hitLine) { }

    /** @return audit rows accumulated by the last run of this runner */
    public final List<PinRow> audit = new ArrayList<>();

    private final FixtureLoader loader;

    /** @param loader loader with the chosen float-domain arm */
    public SuiteRunner(FixtureLoader loader) {
        this.loader = loader;
    }

    /**
     * Run the two-phase suite.
     *
     * @param verbose print per-fixture verdicts (false = summary line only)
     * @return failure count (0 = green)
     */
    public int run(String label, Path validDir, Path invalidDir, Checker checker,
                   int pinnedValid, int pinnedInvalid, boolean verbose) {
        List<Path> valid = jsonFiles(validDir);
        List<Path> invalid = jsonFiles(invalidDir);
        if (valid.isEmpty() || invalid.isEmpty()) {
            System.out.printf("[%s] suite incomplete: need at least one valid and one "
                    + "invalid example%n", label);
            return 1;
        }
        int bad = 0;
        for (Path f : valid) {
            FixtureLoader.Loaded loaded = loader.load(f);
            if (loaded.doc() == null || loaded.error() != null) {
                if (verbose) {
                    System.out.printf("[%s] FAIL must-accept %s  (%s)%n", label,
                            f.getFileName(), loaded.error());
                }
                bad++;
                continue;
            }
            List<String> errs = checker.apply(loaded.doc());
            if (!errs.isEmpty()) {
                if (verbose) {
                    System.out.printf("[%s] FAIL must-accept %s%n", label, f.getFileName());
                    errs.forEach(e -> System.out.println("      " + e));
                }
                bad++;
            } else if (verbose) {
                System.out.printf("[%s] PASS must-accept %s%n", label, f.getFileName());
            }
        }
        for (Path f : invalid) {
            FixtureLoader.Loaded loaded = loader.load(f);
            String name = f.getFileName().toString();
            if (loaded.doc() != null && loaded.error() != null) {
                if (verbose) {
                    System.out.printf("[%s] FAIL must-reject %s  (%s — an unreadable pin "
                            + "cannot verify the rejection)%n", label, name, loaded.error());
                }
                bad++;
                continue;
            }
            List<String> errs = loaded.doc() == null
                    ? List.of(String.valueOf(loaded.error()))
                    : checker.apply(loaded.doc());
            String pin = loaded.pin();
            String hitLine = errs.stream().filter(e -> pin != null && e.contains(pin))
                    .findFirst().orElse(null);
            boolean hit = pin == null || hitLine != null;
            audit.add(new PinRow(label, name, pin == null ? "<none>" : pin,
                    pin == null ? "NONE" : PinAudit.classify(label, pin), hit, hitLine));
            if (errs.isEmpty()) {
                if (verbose) {
                    System.out.printf("[%s] FAIL must-reject %s  (was accepted!)%n",
                            label, name);
                }
                bad++;
            } else if (!hit) {
                if (verbose) {
                    System.out.printf("[%s] FAIL must-reject %s  (rejected for the wrong "
                            + "reason: %s lacks '%s')%n", label, name, errs.get(0), pin);
                }
                bad++;
            } else if (verbose) {
                System.out.printf("[%s] PASS must-reject %s  (%s)%n", label, name, errs.get(0));
            }
        }
        System.out.printf("[%s] %d must-accept + %d must-reject, %d failures%n",
                label, valid.size(), invalid.size(), bad);
        if (valid.size() != pinnedValid || invalid.size() != pinnedInvalid) {
            System.out.printf("[%s] FAIL corpus count %d+%d != pinned %d+%d "
                    + "(corpus count changed?)%n", label, valid.size(), invalid.size(),
                    pinnedValid, pinnedInvalid);
            bad++;
        }
        return bad;
    }

    private static List<Path> jsonFiles(Path dir) {
        try (var stream = Files.list(dir)) {
            return stream.filter(p -> p.toString().endsWith(".json"))
                    .sorted(Comparator.comparing(p -> p.getFileName().toString()))
                    .toList();
        } catch (IOException e) {
            throw new UncheckedIOExceptionAdapter(e);
        }
    }

    private static final class UncheckedIOExceptionAdapter extends RuntimeException {
        UncheckedIOExceptionAdapter(IOException cause) {
            super(cause);
        }
    }
}
