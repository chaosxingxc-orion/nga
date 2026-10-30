// Package schemalib is the growth layer's shared JSON-Schema compilation
// entry (pieces 2-6). The engine is santhosh-tekuri/jsonschema with the
// dlclark/regexp2 regexp engine: .NET '$' semantics match Python's re on a
// trailing newline, so the dual validators cannot fork on the digest
// pattern the way Go's default RE2 would (the parity target the frozen base
// legislated as V3 MAJOR-1; R1 M-6 found the ledger and adoption checkers
// had silently compiled with RE2). The frozen base keeps its private copy in
// internal/validate — this package is the growth layer's single engine, not
// a refactor of the base.
//
// Lazy compiles once, under a lock — R1 m-8: both checkers had unguarded
// lazy compile, a data race on first concurrent use.
package schemalib

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"

	"github.com/dlclark/regexp2"
	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

// dlclarkRegexp adapts regexp2 to the santhosh engine interface.
type dlclarkRegexp regexp2.Regexp

func (re *dlclarkRegexp) MatchString(s string) bool {
	matched, err := (*regexp2.Regexp)(re).MatchString(s)
	return err == nil && matched
}

func (re *dlclarkRegexp) String() string { return (*regexp2.Regexp)(re).String() }

// dlclarkCompile compiles one pattern in .NET default mode — its '$' matches
// before a single trailing newline exactly like Python's re.
func dlclarkCompile(s string) (jsonschema.Regexp, error) {
	re, err := regexp2.Compile(s, regexp2.None)
	if err != nil {
		return nil, err
	}
	return (*dlclarkRegexp)(re), nil
}

// Compile compiles a self-contained schema document under its $id. The
// growth-layer schemas carry no cross-document $refs (frozen-engine stake
// C5-a), so a single AddResource is the whole job.
func Compile(id string, doc any) (*jsonschema.Schema, error) {
	c := jsonschema.NewCompiler()
	c.UseRegexpEngine(dlclarkCompile)
	if err := c.AddResource(id, doc); err != nil {
		return nil, err
	}
	return c.Compile(id)
}

// FindSchema locates schema/<name> by CWD probe (the same roots the base
// packages probe: run from a cmd/ or an internal package directory).
func FindSchema(name string) string {
	for _, root := range []string{"../../schema", "../../../schema", "../schema", "."} {
		p := filepath.Join(root, name)
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// Lazy is a compile-once schema handle, safe for concurrent use. Get returns
// the compiled schema or the compile error, stably across calls.
type Lazy struct {
	once   sync.Once
	id     string
	path   string
	schema *jsonschema.Schema
	err    error
}

// NewLazy binds a schema $id to a file path (empty path = always fails
// closed on Get).
func NewLazy(id, path string) *Lazy {
	return &Lazy{id: id, path: path}
}

// Get compiles on first call and returns the cached result afterwards.
func (l *Lazy) Get() (*jsonschema.Schema, error) {
	l.once.Do(func() {
		if l.path == "" {
			l.err = os.ErrNotExist
			return
		}
		raw, err := os.ReadFile(l.path)
		if err != nil {
			l.err = err
			return
		}
		var doc any
		if err := json.Unmarshal(raw, &doc); err != nil {
			l.err = err
			return
		}
		l.schema, l.err = Compile(l.id, doc)
	})
	if l.err != nil {
		return nil, l.err
	}
	return l.schema, nil
}

// Validate checks doc against the compiled schema. An unavailable schema is
// a fail-closed error, never a pass.
func (l *Lazy) Validate(doc any) error {
	s, err := l.Get()
	if err != nil {
		return err
	}
	return s.Validate(doc)
}
