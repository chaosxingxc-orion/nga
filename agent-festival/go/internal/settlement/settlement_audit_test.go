package settlement

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
	"time"
)

const (
	// envLedgerOverride points the audit at a synthetic ledger (the tamper
	// harness uses it); the execution copy is still the real working tree.
	envLedgerOverride = "SETTLEMENT_AUDIT_LEDGER"
	// envNested is set on every token subprocess: a nested audit run does
	// presence+grammar only, so a token that re-invokes the audit cannot
	// recurse (one level, then degrade to the cheap checks).
	envNested = "SETTLEMENT_AUDIT_NESTED"

	protocolPin = "清偿证明协议"
	minSection  = 56 // protocol effective date: R56 起，不追溯
	ledgerName  = "docs/minor-ledger.md"
)

var (
	sectionRe = regexp.MustCompile(`^## R(\d+)\b`)
	// bulletRe matches numeric AND letter-suffix entry ids (M-1/M-A/M-B —
	// the ledger's established letter-id convention, e.g. R17 M-A/M-B/M-C):
	// a scoped letter entry without a token must be presence-checked, not
	// silently invisible to the audit.
	bulletRe = regexp.MustCompile(`^\s*- \*\*([BM])-([A-Za-z0-9]+)`)
	// tokenRe is the canonical grammar. The expectation is EXACT: FAIL or OK.
	// Anything else (prose like "输出含 FAIL") is a grammar violation — the
	// machine contract has no room for narrative.
	tokenRe     = regexp.MustCompile(`\[mutation-proof:\s*(.+?)\s*→\s*(FAIL|OK)\s*\]`)
	inlineRe    = regexp.MustCompile("`[^`]*`") // backtick spans are documentation, not tokens
	retiredMark = "[retired-by:"
)

type token struct {
	cmd     string
	expect  string // "FAIL" | "OK"
	lineNo  int    // 1-based, in the ledger file
	retired bool
	entry   string // owning B/M entry id ("" = section-level token)
}

type violation struct {
	kind  string // presence | grammar | execution | pin | scope
	where string
	msg   string
}

func (v violation) String() string {
	return fmt.Sprintf("settlement-audit/%s: %s — %s", v.kind, v.where, v.msg)
}

type audit struct {
	activeTokens []token
	violations   []violation
	sectionCount int
}

// parseLedger splits the ledger into R-numbered sections, keeps minSection
// and later, and extracts: B/M settlement entries (for the presence check),
// mutation-proof tokens (active and retired), and grammar violations.
func parseLedger(data []byte) *audit {
	a := &audit{}
	lines := strings.Split(string(data), "\n")

	type entry struct {
		id       string
		start    int
		tokCount int
	}
	var curEntry *entry
	curSection := ""
	curScoped := false
	inFence := false

	flush := func() {
		if curEntry != nil && curScoped && curEntry.tokCount == 0 {
			a.violations = append(a.violations, violation{
				kind: "presence", where: curEntry.id,
				msg: "no active mutation-proof token on this settlement entry (protocol: missing token = automatic M)",
			})
		}
		curEntry = nil
	}

	for i, raw := range lines {
		lineNo := i + 1
		// R58 M-2 fence legislation: a fenced code block is documentation,
		// never tokens. A line whose trimmed text starts with "```" toggles
		// fence state; while inside a fence nothing is parsed — no section
		// headers, no bullet entries, no token extraction, no grammar
		// check. A fenced syntax example containing
		// "[mutation-proof: <cmd> → FAIL]" previously parsed as a live
		// token whose literal placeholder failed under bash (exit 1) and
		// false-satisfied the FAIL expectation — false presence, false
		// execution. Only "```" toggles: the ledger uses no "~~~" fences,
		// and recognizing exactly one form keeps the state machine
		// single-form and auditable.
		if strings.HasPrefix(strings.TrimSpace(raw), "```") {
			inFence = !inFence
			continue
		}
		if inFence {
			continue
		}
		if m := sectionRe.FindStringSubmatch(raw); m != nil {
			flush()
			if atoi(m[1]) >= minSection {
				a.sectionCount++
			}
			curSection = strings.TrimPrefix(raw, "## ")
			curScoped = atoi(m[1]) >= minSection
			continue
		}
		if curSection == "" {
			continue // header material before the first R-section
		}

		if m := bulletRe.FindStringSubmatch(raw); m != nil && curScoped {
			flush()
			curEntry = &entry{id: fmt.Sprintf("%s %s-%s", curSection, m[1], m[2]), start: lineNo}
		}

		// Backtick spans are documentation (the protocol header quotes the
		// grammar itself) — strip before token extraction.
		cleaned := inlineRe.ReplaceAllString(raw, "")
		matches := tokenRe.FindAllStringSubmatch(cleaned, -1)
		retired := strings.Contains(raw, retiredMark)
		if len(matches) == 0 && strings.Contains(cleaned, "[mutation-proof:") && !retired && curScoped {
			a.violations = append(a.violations, violation{
				kind: "grammar", where: fmt.Sprintf("%s:%d", ledgerName, lineNo),
				msg: "mutation-proof marker is not machine-parseable — canonical forms: [mutation-proof: <cmd> → FAIL] or [mutation-proof: <cmd> → OK]",
			})
			continue
		}
		for _, m := range matches {
			if retired {
				continue // historical token; its carrier is retired, proof superseded
			}
			tk := token{cmd: m[1], expect: m[2], lineNo: lineNo, retired: false}
			if curEntry != nil && lineNo >= curEntry.start {
				tk.entry = curEntry.id
				curEntry.tokCount++
			}
			a.activeTokens = append(a.activeTokens, tk)
		}
	}
	flush()
	return a
}

func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			break
		}
		n = n*10 + int(c-'0')
	}
	return n
}

func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("settlement audit: cannot locate own source file")
	}
	// <root>/agent-festival/go/internal/settlement/settlement_audit_test.go
	root := filepath.Dir(file)
	for i := 0; i < 4; i++ {
		root = filepath.Dir(root)
	}
	return root
}

// copyWorkingTree snapshots the working tree (tracked + untracked, gitignore
// respected) into dest. Tokens mutate source files; they must never touch
// the real tree, so they run against this copy. Content comes from disk
// (not the index), so uncommitted work is audited exactly as the author
// sees it — in CI a clean checkout makes this identical to HEAD.
func copyWorkingTree(t *testing.T, root, dest string) {
	t.Helper()
	cmd := exec.Command("git", "ls-files", "-co", "-z", "--exclude-standard")
	cmd.Dir = root
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("settlement audit: git ls-files: %v", err)
	}
	for _, rel := range bytes.Split(out, []byte{0}) {
		if len(rel) == 0 {
			continue
		}
		src := filepath.Join(root, string(rel))
		info, err := os.Lstat(src)
		if err != nil || !info.Mode().IsRegular() {
			continue // raced deletion, symlink, or directory
		}
		dst := filepath.Join(dest, string(rel))
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			t.Fatalf("settlement audit: mkdir: %v", err)
		}
		data, err := os.ReadFile(src)
		if err != nil {
			continue // raced deletion between Lstat and Read
		}
		if err := os.WriteFile(dst, data, 0o644); err != nil {
			t.Fatalf("settlement audit: write copy: %v", err)
		}
	}
}

// runShell executes script via bash in dir; returns (exit code, combined
// output, error). Exit code -1 means the process could not be launched or
// hit the timeout.
func runShell(dir string, extraEnv []string, script string, timeout time.Duration) (int, string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, "bash", "-c", script)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), extraEnv...)
	var buf bytes.Buffer
	cmd.Stdout, cmd.Stderr = &buf, &buf
	runErr := cmd.Run()
	out := buf.String()
	if runErr == nil {
		return 0, out, nil
	}
	var ee *exec.ExitError
	if errors.As(runErr, &ee) {
		return ee.ExitCode(), out, nil
	}
	return -1, out, runErr
}

func runToken(dir string, tk token) (bool, string) {
	rc, out, err := runShell(dir, []string{envNested + "=1"}, tk.cmd, 5*time.Minute)
	if err != nil {
		return false, fmt.Sprintf("launch/timeout: %v\noutput tail: %s", err, tail(out))
	}
	wantFail := tk.expect == "FAIL"
	if (rc != 0) == wantFail {
		return true, ""
	}
	return false, fmt.Sprintf("want exit %s, got %d\noutput tail: %s",
		map[bool]string{true: "≠0 (FAIL)", false: "=0 (OK)"}[wantFail], rc, tail(out))
}

func tail(s string) string {
	if len(s) > 800 {
		return s[len(s)-800:]
	}
	return s
}

// TestSettlementAudit is the protocol's machine half: presence (every B/M
// settlement from R56 on carries an active token), grammar (canonical
// forms only), and validity (every active token re-runs to its declared
// outcome inside a working-tree copy).
func TestSettlementAudit(t *testing.T) {
	if testing.Short() {
		t.Skip("settlement audit re-runs every mutation-proof token (~2min); skipped under -short")
	}
	ledgerPath := os.Getenv(envLedgerOverride)
	if ledgerPath == "" {
		ledgerPath = filepath.Join(repoRoot(t), "agent-festival", "docs", "minor-ledger.md")
	}
	data, err := os.ReadFile(ledgerPath)
	if err != nil {
		t.Fatalf("settlement audit: read ledger: %v", err)
	}
	a := parseLedger(data)
	// The protocol-pin check applies only to the real ledger — synthetic
	// tamper ledgers legitimately omit the header paragraph.
	if os.Getenv(envLedgerOverride) == "" && !strings.Contains(string(data), protocolPin) {
		a.violations = append(a.violations, violation{
			kind: "pin", where: ledgerName,
			msg: "the settlement-proof protocol paragraph vanished from the ledger header",
		})
	}
	if a.sectionCount == 0 {
		a.violations = append(a.violations, violation{
			kind: "scope", where: ledgerName,
			msg: fmt.Sprintf("no R%d+ sections found — the protocol's scope vanished from the ledger", minSection),
		})
	}

	// The execution phase is skipped for nested invocations (a token that
	// re-runs the audit must not recurse); presence and grammar still run.
	if os.Getenv(envNested) == "" {
		execRoot := t.TempDir()
		if os.Getenv(envLedgerOverride) == "" {
			// Real-audit context: tokens mutate source files, so they run
			// against a working-tree copy (the real tree is never touched).
			copyWorkingTree(t, repoRoot(t), execRoot)
		}
		// Harness context (SETTLEMENT_AUDIT_LEDGER set, i.e. the tamper
		// battery): synthetic tokens are echo/false-style and cwd-
		// independent — a plain temp dir suffices. A harness run may be
		// nested inside a copy with no .git, where the git-based copy is
		// impossible; the real audit still fails loud without git.
		for _, tk := range a.activeTokens {
			if ok, detail := runToken(execRoot, tk); !ok {
				where := tk.entry
				if where == "" {
					where = fmt.Sprintf("%s:%d (section-level)", ledgerName, tk.lineNo)
				}
				a.violations = append(a.violations, violation{
					kind: "execution", where: where,
					msg: fmt.Sprintf("token cmd %q did not reproduce its declared outcome: %s", tk.cmd, detail),
				})
			}
		}
	}

	if len(a.violations) > 0 {
		var b strings.Builder
		fmt.Fprintf(&b, "settlement audit: %d violation(s)", len(a.violations))
		for _, v := range a.violations {
			fmt.Fprintf(&b, "\n%s", v.String())
		}
		t.Fatal(b.String())
	}
}

// TestSettlementAuditSelfTest exercises the parser and the executor on
// synthetic ledgers — the tamper faces, in-process and fast:
// presence-miss (numeric and letter-suffix entry ids), the fenced-only
// proof, the echo-FAIL fake (exit 0 masquerading as FAIL), the false-OK
// fake (exit 1 masquerading as OK), grammar drift, retired-token skipping,
// and the two passing controls.
func TestSettlementAuditSelfTest(t *testing.T) {
	cwd := t.TempDir()

	t.Run("presence_miss_detected", func(t *testing.T) {
		a := parseLedger([]byte("## R56 复审记账\n- **M-1（no token）**: settled without proof.\n"))
		if len(a.violations) != 1 || a.violations[0].kind != "presence" {
			t.Fatalf("want exactly one presence violation, got %+v", a.violations)
		}
	})
	t.Run("echo_fail_fake_detected", func(t *testing.T) {
		a := parseLedger([]byte("## R56 复审记账\n- **M-1**: settled.\n  [mutation-proof: echo FAIL → FAIL]\n"))
		if len(a.activeTokens) != 1 {
			t.Fatalf("want 1 active token, got %+v", a.activeTokens)
		}
		if ok, _ := runToken(cwd, a.activeTokens[0]); ok {
			t.Fatal("echo FAIL (exit 0) must NOT satisfy a → FAIL token — the exit-code check is the echo-killer")
		}
	})
	t.Run("false_ok_fake_detected", func(t *testing.T) {
		a := parseLedger([]byte("## R56 复审记账\n- **M-1**: settled.\n  [mutation-proof: false → OK]\n"))
		if ok, _ := runToken(cwd, a.activeTokens[0]); ok {
			t.Fatal("false (exit 1) must NOT satisfy a → OK token")
		}
	})
	t.Run("grammar_drift_detected", func(t *testing.T) {
		a := parseLedger([]byte("## R56 复审记账\n- **M-1**: settled.\n  [mutation-proof: echo hi → 输出含 FAIL]\n"))
		var found bool
		for _, v := range a.violations {
			if v.kind == "grammar" {
				found = true
			}
		}
		if !found {
			t.Fatalf("narrative expectation must be a grammar violation, got %+v", a.violations)
		}
	})
	t.Run("backtick_documentation_not_a_token", func(t *testing.T) {
		// The protocol header quotes the grammar inside backticks; that must
		// never parse as an executable token (its <cmd> placeholder would
		// exit 127 and false-pass a → FAIL check).
		a := parseLedger([]byte("## R56 复审记账\nprose quoting `[mutation-proof: <可复跑命令> → FAIL]` as documentation.\n- **M-1**: settled.\n  [mutation-proof: exit 3 → FAIL]\n"))
		if len(a.activeTokens) != 1 {
			t.Fatalf("backticked grammar quote must not become a token; got %+v", a.activeTokens)
		}
		if ok, _ := runToken(cwd, a.activeTokens[0]); !ok {
			t.Fatal("exit 3 must satisfy → FAIL")
		}
	})
	t.Run("letter_entry_without_token_detected", func(t *testing.T) {
		// R58 M-1: letter-suffix entry ids (the ledger's letter convention,
		// e.g. R17 M-A/M-B/M-C) are legal syntax — a scoped letter entry
		// with no token must trip presence, not pass invisibly.
		a := parseLedger([]byte("## R56 review ledger\n- **M-A**: settled without proof.\n"))
		if len(a.violations) != 1 || a.violations[0].kind != "presence" {
			t.Fatalf("letter-suffix entry must be presence-checked, got %+v", a.violations)
		}
		if !strings.Contains(a.violations[0].where, "M-A") {
			t.Fatalf("violation must carry the letter entry id, got %q", a.violations[0].where)
		}
	})
	t.Run("fenced_proof_not_a_token", func(t *testing.T) {
		// R58 M-2: fence content is documentation — a fenced token line
		// parses as nothing, and the entry's proof obligation stands
		// (presence), even though the fenced <cmd> placeholder would exit
		// non-zero and false-satisfy a FAIL expectation if it were counted.
		a := parseLedger([]byte("## R56 review ledger\n- **M-1**: settled.\n```\n[mutation-proof: <cmd> → FAIL]\n```\n"))
		if len(a.activeTokens) != 0 {
			t.Fatalf("fenced token must not become an active token; got %+v", a.activeTokens)
		}
		if len(a.violations) != 1 || a.violations[0].kind != "presence" {
			t.Fatalf("fenced-only proof must leave the presence obligation standing, got %+v", a.violations)
		}
	})
	t.Run("retired_token_skipped", func(t *testing.T) {
		a := parseLedger([]byte("## R56 复审记账\n- **M-1**: settled.\n  [mutation-proof: false → FAIL] [retired-by: deadbeef superseded]\n  [mutation-proof: exit 3 → FAIL]\n"))
		if len(a.activeTokens) != 1 {
			t.Fatalf("retired token must be excluded; got %+v", a.activeTokens)
		}
		if len(a.violations) != 0 {
			t.Fatalf("entry with an active successor token is settled; got %+v", a.violations)
		}
	})
	t.Run("controls_pass", func(t *testing.T) {
		led := "## R56 复审记账\n- **M-1**: settled.\n  [mutation-proof: exit 3 → FAIL]\n- **M-2**: settled.\n  [mutation-proof: true → OK]\n"
		a := parseLedger([]byte(led))
		if len(a.violations) != 0 {
			t.Fatalf("controls must be clean, got %+v", a.violations)
		}
		for _, tk := range a.activeTokens {
			if ok, detail := runToken(cwd, tk); !ok {
				t.Fatalf("control token %q failed: %s", tk.cmd, detail)
			}
		}
	})
}
