// Package compose synthesizes an execution graph into one contract and judges admissibility.
// It is the Go successor of schema/compose.py (frozen oracle): same examples,
// same _expect_match / _expect_composed pins, same integer budget arithmetic.
package compose

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"festival-dev/go/internal/validate"
)

// ---------- constants ----------

var levelRank = validate.LevelRank
var compensationRank = map[string]int{"none": 0, "manual": 1, "automatic": 2}

var summedBounds = []string{"max_cost", "max_downstream_calls", "max_bytes_out"}

const timeBound = "max_seconds"
const safeIntMax = 9007199254740991

var graphSchema map[string]any
var ExamplesDir string

func init() {
	for _, root := range []string{".", "..", "../..", "../../.."} { // last root: go test runs from cmd/<x>/
		d := filepath.Join(root, "schema")
		if _, err := os.Stat(filepath.Join(d, "execution-graph.schema.json")); err == nil {
			ExamplesDir = filepath.Join(d, "examples")
			raw, _ := os.ReadFile(filepath.Join(d, "execution-graph.schema.json"))
			json.Unmarshal(raw, &graphSchema)
			return
		}
	}
}

// RegisterGraph hands the loaded schema to the library cross-check; failures
// are non-fatal here — CheckGraphVerdict fails closed if registration failed.
func RegisterGraph() {
	if graphSchema != nil {
		_ = validate.RegisterGraphSchema(graphSchema)
	}
}

// ---------- grant atoms ----------

// atom is the key for a grant: (kind, selector, action).
type atom struct{ kind, selector, action string }

func atomicGrants(grants []any) map[atom]string {
	out := map[atom]string{}
	for _, gAny := range grants {
		g, ok := gAny.(map[string]any)
		if !ok {
			continue
		}
		res, _ := g["resource"].(map[string]any)
		if res == nil {
			continue
		}
		kind, _ := res["kind"].(string)
		selector, _ := res["selector"].(string)
		actions, _ := g["actions"].([]any)
		effect, _ := g["effect"].(string)
		for _, aAny := range actions {
			action, _ := aAny.(string)
			k := atom{kind, selector, action}
			mergeWorst(out, k, effect)
		}
	}
	return out
}

func sortedAtoms(m map[atom]string) []atom {
	keys := make([]atom, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].kind != keys[j].kind {
			return keys[i].kind < keys[j].kind
		}
		if keys[i].selector != keys[j].selector {
			return keys[i].selector < keys[j].selector
		}
		return keys[i].action < keys[j].action
	})
	return keys
}

func mergeWorst(into map[atom]string, key atom, effect string) {
	if cur, has := into[key]; !has || levelRank[effect] > levelRank[cur] {
		into[key] = effect
	}
}

// ---------- plan tree ----------

// planStep is one (mode, index) step in a plan path.
type planStep struct {
	mode string
	idx  int
}

func planIDs(plan any) []string {
	if s, ok := plan.(string); ok {
		return []string{s}
	}
	m, ok := plan.(map[string]any)
	if !ok {
		return nil
	}
	var children []any
	if c, ok := m["seq"].([]any); ok {
		children = c
	} else if c, ok := m["par"].([]any); ok {
		children = c
	}
	var out []string
	for _, c := range children {
		out = append(out, planIDs(c)...)
	}
	return out
}

func planPaths(plan any, prefix []planStep) map[string][]planStep {
	if s, ok := plan.(string); ok {
		return map[string][]planStep{s: prefix}
	}
	m, ok := plan.(map[string]any)
	if !ok {
		return map[string][]planStep{}
	}
	mode := "seq"
	var children []any
	if c, ok := m["seq"].([]any); ok {
		children = c
	} else if c, ok := m["par"].([]any); ok {
		mode = "par"
		children = c
	}
	out := map[string][]planStep{}
	for i, c := range children {
		sub := planPaths(c, append(append([]planStep{}, prefix...), planStep{mode, i}))
		for k, v := range sub {
			out[k] = v
		}
	}
	return out
}

// ---------- compose requires ----------

func composeRequires(nodes map[string]map[string]any, edges [][]string, plan any) (map[atom]string, []string) {
	suppliers := map[string][]string{}
	for _, e := range edges {
		if len(e) == 2 {
			suppliers[e[1]] = append(suppliers[e[1]], e[0])
		}
	}
	effective := map[string]map[atom]string{}
	merged := map[atom]string{}
	var errs []string
	for _, nodeID := range planIDs(plan) {
		heldUpstream := map[atom]string{}
		for _, s := range suppliers[nodeID] {
			for key, effect := range effective[s] {
				mergeWorst(heldUpstream, key, effect)
			}
		}
		own := map[atom]string{}
		contract, _ := nodes[nodeID]
		if contract == nil {
			continue
		}
		requires, _ := contract["requires"].([]any)
		for _, gAny := range requires {
			g, ok := gAny.(map[string]any)
			if !ok {
				continue
			}
			gAtoms := atomicGrants([]any{g})
			suppliedBy, _ := g["supplied_by"].(string)
			for _, key := range sortedAtoms(gAtoms) {
				effect := gAtoms[key]
				mergeWorst(merged, key, effect)
				if suppliedBy != "upstream" {
					mergeWorst(own, key, effect)
					continue
				}
				if _, held := heldUpstream[key]; !held {
					errs = append(errs, fmt.Sprintf("node %s declares %s:%s action=%s as upstream-supplied, but no supplier (source of an incoming edge) holds it with that action",
						nodeID, key.kind, key.selector, key.action))
				} else if levelRank[heldUpstream[key]] < levelRank[effect] {
					errs = append(errs, fmt.Sprintf("node %s declares %s:%s action=%s as upstream-supplied at effect %s, but its supplier holds it at %s",
						nodeID, key.kind, key.selector, key.action, effect, heldUpstream[key]))
				} else {
					mergeWorst(own, key, effect)
				}
			}
		}
		effective[nodeID] = own
	}
	return merged, errs
}

// ---------- compose effects ----------

func composeEffects(nodes map[string]map[string]any) map[string]any {
	maxLevel := 0
	for _, c := range nodes {
		effects, _ := c["effects"].(map[string]any)
		if effects == nil {
			continue
		}
		level, _ := effects["level"].(string)
		if r, ok := levelRank[level]; ok && r > maxLevel {
			maxLevel = r
		}
	}
	levelName := "none"
	for k, v := range levelRank {
		if v == maxLevel {
			levelName = k
		}
	}
	if levelName == "none" {
		return map[string]any{"level": "none"}
	}
	bestComp := "automatic"
	for _, c := range nodes {
		effects, _ := c["effects"].(map[string]any)
		if effects == nil {
			continue
		}
		level, _ := effects["level"].(string)
		if level == "none" {
			continue
		}
		comp, _ := effects["compensation"].(string)
		if compensationRank[comp] < compensationRank[bestComp] {
			bestComp = comp
		}
	}
	return map[string]any{"level": levelName, "compensation": bestComp}
}

// ---------- compose bounds ----------

func normalizeBounds(bounds map[string]any) map[string]any {
	out := map[string]any{}
	for name, v := range bounds {
		if name == "max_cost" {
			m, ok := v.(map[string]any)
			if !ok {
				panic(fmt.Sprintf("max_cost must be an object with amount+unit (schema-enforced shape; programmatic callers must pass it — got %T)", v))
			}
			unit, _ := m["unit"].(string)
			out[name] = map[string]any{"amount": anyToInt64(m["amount"]), "unit": unit}
		} else {
			out[name] = anyToInt64(v)
		}
	}
	return out
}

func boundAmount(b map[string]any, name string) (int64, bool) {
	v, has := b[name]
	if !has || v == nil {
		return 0, false
	}
	if m, ok := v.(map[string]any); ok {
		return anyToInt64(m["amount"]), true
	}
	if f, ok := v.(float64); ok {
		return anyToInt64(f), true // saturated conversion (V27 claim, landed V28: bare int64(f) wraps negative on amd64)
	}
	if i, ok := v.(int64); ok {
		return i, true
	}
	if i, ok := v.(int); ok {
		return int64(i), true // programmatic callers (V9 M-1: an int parent bound must still bound)
	}
	return 0, false
}

// addSat adds two bound amounts, saturating on int64 overflow. Each individual
// amount is schema-capped at 2^53-1, but a seq sum is not; Python folds with
// unlimited ints and the child > parent comparison then rejects it, while a
// wrapped-around negative would sail under any parent (V2 M5). A saturated
// MaxInt64 exceeds every legal bound, which is exactly the comparison verdict
// the oracle produces for the true (larger) sum.
func addSat(a, b int64) int64 {
	s := a + b
	if (a > 0 && b > 0 && s < 0) || (a < 0 && b < 0 && s >= 0) {
		if a > 0 {
			return math.MaxInt64
		}
		return math.MinInt64
	}
	return s
}

func foldBounds(plan any, nodes map[string]map[string]any) (map[string]any, error) {
	if s, ok := plan.(string); ok {
		contract, _ := nodes[s]
		if contract == nil {
			return nil, fmt.Errorf("plan references unknown node %s", s)
		}
		bounds, _ := contract["bounds"].(map[string]any)
		if bounds == nil {
			bounds = map[string]any{}
		}
		return normalizeBounds(bounds), nil
	}
	m, ok := plan.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("malformed plan node")
	}
	mode := "seq"
	var children []any
	if c, ok := m["seq"].([]any); ok {
		children = c
	} else if c, ok := m["par"].([]any); ok {
		mode = "par"
		children = c
	}
	parts := make([]map[string]any, 0, len(children))
	for _, c := range children {
		p, err := foldBounds(c, nodes)
		if err != nil {
			return nil, err
		}
		parts = append(parts, p)
	}

	out := map[string]any{}
	for _, name := range summedBounds {
		if name == "max_cost" {
			units := map[string]bool{}
			allPresent := true
			for _, p := range parts {
				if _, has := p["max_cost"]; !has {
					allPresent = false
					break
				}
				if cm, ok := p["max_cost"].(map[string]any); ok {
					u, _ := cm["unit"].(string)
					units[u] = true
				}
			}
			if !allPresent {
				continue
			}
			if len(units) != 1 {
				us := make([]string, 0, len(units))
				for u := range units {
					us = append(us, u)
				}
				sort.Strings(us)
				return nil, fmt.Errorf("max_cost units differ across branches: %v; convert to one unit before composing", us)
			}
			var total int64
			unit := ""
			for _, p := range parts {
				cm, ok := p["max_cost"].(map[string]any)
				if !ok {
					panic(fmt.Sprintf("max_cost must be an object (schema-enforced; got %T)", p["max_cost"]))
				}
				total = addSat(total, cm["amount"].(int64))
				unit, _ = cm["unit"].(string)
			}
			out["max_cost"] = map[string]any{"amount": total, "unit": unit}
		} else {
			allPresent := true
			var total int64
			for _, p := range parts {
				v, has := p[name]
				if !has {
					allPresent = false
					break
				}
				total = addSat(total, v.(int64))
			}
			if allPresent {
				out[name] = total
			}
		}
	}
	// time: seq = sum, par = max
	allPresent := true
	var timeVal int64
	for _, p := range parts {
		v, has := p[timeBound]
		if !has {
			allPresent = false
			break
		}
		t := v.(int64)
		if mode == "seq" {
			timeVal = addSat(timeVal, t)
		} else if t > timeVal {
			timeVal = t
		}
	}
	if allPresent {
		out[timeBound] = timeVal
	}
	return out, nil
}

// ---------- admissibility ----------

func subsetViolations(wanted map[atom]string, held []any) []string {
	heldAtoms := atomicGrants(held)
	var errs []string
	for _, key := range sortedAtoms(wanted) {
		effect := wanted[key]
		if _, held := heldAtoms[key]; !held {
			errs = append(errs, fmt.Sprintf("not held by caller: %s:%s action=%s", key.kind, key.selector, key.action))
			continue
		}
		heldEffect := heldAtoms[key]
		if levelRank[effect] > levelRank[heldEffect] {
			errs = append(errs, fmt.Sprintf("effect escalation: %s:%s action=%s wants %s, caller holds %s",
				key.kind, key.selector, key.action, effect, heldEffect))
		}
	}
	return errs
}

func boundsViolations(graphBounds, parentBounds map[string]any, where string) []string {
	var errs []string
	if amount, ok := boundAmount(graphBounds, "max_cost"); ok && amount > safeIntMax {
		errs = append(errs, fmt.Sprintf("%s: max_cost %d exceeds the safe-integer ceiling %d", where, amount, safeIntMax))
	}
	gcUnit, gcHas := "", false
	if cm, ok := graphBounds["max_cost"].(map[string]any); ok {
		gcUnit, gcHas = cm["unit"].(string)
	}
	pcUnit, pcHas := "", false
	if cm, ok := parentBounds["max_cost"].(map[string]any); ok {
		pcUnit, pcHas = cm["unit"].(string)
	}
	if gcHas && pcHas && gcUnit != pcUnit {
		errs = append(errs, fmt.Sprintf("%s: max_cost unit '%s' differs from parent's '%s'; amounts in different units are not comparable", where, gcUnit, pcUnit))
	}
	for _, name := range append(append([]string{}, summedBounds...), timeBound) {
		parent, has := boundAmount(parentBounds, name)
		if !has {
			continue
		}
		if name == "max_cost" && len(errs) > 0 {
			continue
		}
		child, has := boundAmount(graphBounds, name)
		if !has {
			errs = append(errs, fmt.Sprintf("%s: %s unbounded but parent limits it to %d", where, name, parent))
		} else if child > parent {
			errs = append(errs, fmt.Sprintf("%s: %s %d exceeds parent budget %d", where, name, child, parent))
		}
	}
	return errs
}

func splitBounds(parentBounds map[string]any, n int) map[string]any {
	share := map[string]any{}
	for _, name := range summedBounds {
		if _, has := parentBounds[name]; !has {
			continue
		}
		if name == "max_cost" {
			cm, ok := parentBounds["max_cost"].(map[string]any)
			if !ok {
				panic(fmt.Sprintf("max_cost must be an object (schema-enforced; got %T)", parentBounds["max_cost"]))
			}
			amount := anyToInt64(cm["amount"])
			unit, _ := cm["unit"].(string)
			share[name] = map[string]any{"amount": amount / int64(n), "unit": unit}
		} else if v, has := parentBounds[name]; has {
			share[name] = anyToInt64(v) / int64(n)
		}
	}
	if v, has := parentBounds[timeBound]; has {
		share[timeBound] = anyToInt64(v)
	}
	return share
}

// anyToInt64 converts programmatic numeric values with SATURATION beyond
// int64 (V26 singularity F-4): a bare int64(t) conversion is
// implementation-defined for out-of-range floats (arm64 saturates, amd64
// wraps negative) — the addSat discipline, applied at the conversion edge.
func anyToInt64(v any) int64 {
	switch t := v.(type) {
	case int64:
		return t
	case int:
		return int64(t)
	case float64:
		switch {
		case t != t:
			return 0 // NaN: unreachable past the schema guards; deterministic by default
		case t >= 9223372036854775807.0:
			return math.MaxInt64
		case t <= -9223372036854775808.0:
			return math.MinInt64
		}
		return int64(t)
	}
	return 0
}

func leafAllotments(plan any, parentBounds map[string]any) map[string]map[string]any {
	parentBounds = normalizeBounds(parentBounds) // seq leaves pass it through as-is; ints everywhere (V10 m1)
	out := map[string]map[string]any{}
	var walk func(node any, allotment map[string]any)
	walk = func(node any, allotment map[string]any) {
		if s, ok := node.(string); ok {
			out[s] = allotment
			return
		}
		m, ok := node.(map[string]any)
		if !ok {
			return
		}
		mode := "seq"
		var children []any
		if c, ok := m["seq"].([]any); ok {
			children = c
		} else if c, ok := m["par"].([]any); ok {
			mode = "par"
			children = c
		}
		childAllotment := allotment
		if mode == "par" {
			childAllotment = splitBounds(allotment, len(children))
		}
		for _, c := range children {
			walk(c, childAllotment)
		}
	}
	walk(plan, parentBounds)
	return out
}

func splitViolations(plan any, nodes map[string]map[string]any, parentBounds map[string]any) []string {
	var errs []string
	allot := leafAllotments(plan, parentBounds)
	leaves := make([]string, 0, len(allot))
	for leaf := range allot {
		leaves = append(leaves, leaf)
	}
	sort.Strings(leaves) // deterministic error order (V23 4-lens M-1 sibling)
	for _, leaf := range leaves {
		allotment := allot[leaf]
		contract, _ := nodes[leaf]
		if contract == nil {
			continue
		}
		bounds, _ := contract["bounds"].(map[string]any)
		if bounds == nil {
			bounds = map[string]any{}
		}
		errs = append(errs, boundsViolations(bounds, allotment, fmt.Sprintf("node %s", leaf))...)
	}
	return errs
}

// ---------- shape errors ----------

func sortedNodeIDs(nodes map[string]map[string]any) []string {
	ids := make([]string, 0, len(nodes))
	for id := range nodes {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

func shapeErrors(nodes map[string]map[string]any, edges [][]string, plan any) []string {
	var errs []string
	// plan grammar (exactly one of seq/par) is enforced by execution-graph.schema.json,
	// exactly as the oracle notes at compose.py shape_errors (4-lens V8 F2: dead branch removed)
	scheduled := planIDs(plan)
	nodeIDs := map[string]bool{}
	for id := range nodes {
		nodeIDs[id] = true
	}
	referenced := map[string]bool{}
	for _, id := range scheduled {
		referenced[id] = true
	}
	for _, e := range edges {
		if len(e) == 2 {
			referenced[e[0]] = true
			referenced[e[1]] = true
		}
	}
	var unknown []string
	for id := range referenced {
		if !nodeIDs[id] {
			unknown = append(unknown, id)
		}
	}
	sort.Strings(unknown)
	if len(unknown) > 0 {
		errs = append(errs, fmt.Sprintf("plan/edges reference unknown nodes: %v", unknown))
	}
	scheduledSet := map[string]bool{}
	for _, id := range scheduled {
		scheduledSet[id] = true
	}
	var orphans []string
	for id := range nodes {
		// only the plan schedules (Python: nodes - scheduled); an edge endpoint
		// without a plan slot stays an orphan and must be reported as such (V5 m1)
		if !scheduledSet[id] {
			orphans = append(orphans, id)
		}
	}
	sort.Strings(orphans)
	if len(orphans) > 0 {
		errs = append(errs, fmt.Sprintf("nodes defined but not scheduled in plan: %v", orphans))
	}
	twiceMap := map[string]int{}
	for _, id := range scheduled {
		twiceMap[id]++
	}
	var twice []string
	for id, c := range twiceMap {
		if c > 1 {
			twice = append(twice, id)
		}
	}
	sort.Strings(twice)
	if len(twice) > 0 {
		errs = append(errs, fmt.Sprintf("nodes scheduled more than once in plan: %v; a node runs once per graph", twice))
	}
	if len(errs) > 0 {
		return errs
	}

	paths := planPaths(plan, nil)
	for _, e := range edges {
		if len(e) != 2 {
			continue
		}
		src, dst := e[0], e[1]
		if src == dst {
			errs = append(errs, fmt.Sprintf("self edge %s -> %s", src, dst))
			continue
		}
		ps, pd := paths[src], paths[dst]
		common := 0
		for common < len(ps) && common < len(pd) && ps[common] == pd[common] {
			common++
		}
		if common == len(ps) || common == len(pd) {
			errs = append(errs, fmt.Sprintf("supply edge %s -> %s between a group and its own member", src, dst))
			continue
		}
		ss, sd := ps[common], pd[common]
		if ss.mode == "par" {
			errs = append(errs, fmt.Sprintf("supply edge %s -> %s between parallel siblings cannot be honored at run time", src, dst))
		} else if ss.idx >= sd.idx {
			errs = append(errs, fmt.Sprintf("supply edge %s -> %s runs backwards: %s is scheduled after %s", src, dst, src, dst))
		}
	}

	for _, nodeID := range sortedNodeIDs(nodes) {
		contract := nodes[nodeID]
		requires, _ := contract["requires"].([]any)
		for _, gAny := range requires {
			g, ok := gAny.(map[string]any)
			if !ok {
				continue
			}
			res, _ := g["resource"].(map[string]any)
			if res == nil {
				continue
			}
			kind, _ := res["kind"].(string)
			if kind != "agent" {
				continue
			}
			actions, _ := g["actions"].([]any)
			hasDelegate := false
			for _, a := range actions {
				if s, _ := a.(string); s == "delegate" {
					hasDelegate = true
				}
			}
			if !hasDelegate {
				continue
			}
			target, _ := res["selector"].(string)
			if !nodeIDs[target] {
				errs = append(errs, fmt.Sprintf("node %s delegates to '%s', which is not a node of this graph; closure needs the delegate's contract modeled (ADR-0001 §2.4)", nodeID, target))
			}
		}
	}
	return errs
}

// ---------- top-level compose ----------

type Result struct {
	Errors   []string
	Composed map[string]any
}

func ComposeErrors(doc map[string]any) *Result {
	res := &Result{}
	// schema
	var schemaErrs []string
	validate.SetRootSchema(graphSchema)
	validate.SchemaErrorsDoc(doc, graphSchema, "<root>", &schemaErrs)
	schemaErrs = validate.CheckGraphVerdict(doc, schemaErrs)
	if len(schemaErrs) > 0 {
		res.Errors = schemaErrs
		return res
	}
	nodesRaw, _ := doc["nodes"].(map[string]any)
	nodes := map[string]map[string]any{}
	for k, v := range nodesRaw {
		if m, ok := v.(map[string]any); ok {
			nodes[k] = m
		}
	}
	var edges [][]string
	if edgesRaw, ok := doc["edges"].([]any); ok {
		for _, e := range edgesRaw {
			if ea, ok := e.([]any); ok && len(ea) == 2 {
				s, _ := ea[0].(string)
				d, _ := ea[1].(string)
				edges = append(edges, []string{s, d})
			}
		}
	}
	plan := doc["plan"]
	for _, nodeID := range sortedNodeIDs(nodes) {
		contract := nodes[nodeID]
		for _, e := range validate.ContractErrors(contract) {
			res.Errors = append(res.Errors, fmt.Sprintf("nodes/%s/%s", nodeID, strings.TrimPrefix(e, "<root>/")))
		}
	}
	if len(res.Errors) > 0 {
		return res
	}
	res.Errors = append(res.Errors, shapeErrors(nodes, edges, plan)...)
	// caller_holds is optional (the schema requires only nodes/plan): absent means
	// the caller holds nothing, and the admissibility gate then reports every
	// wanted atom as not held — it must still RUN (V2 B1).
	callerHolds, _ := doc["caller_holds"].([]any)
	res.Errors = append(res.Errors, validate.GrantErrors(callerHolds, "caller_holds")...)
	if pbm, ok := doc["parent_bounds"].(map[string]any); ok {
		res.Errors = append(res.Errors, parentBoundsFiniteErrors(pbm)...)
	}
	if len(res.Errors) > 0 {
		return res
	}

	bounds, err := foldBounds(plan, nodes)
	if err != nil {
		res.Errors = append(res.Errors, err.Error())
		return res
	}
	requires, reqErrs := composeRequires(nodes, edges, plan)
	reqStr := map[string]any{}
	for k, v := range requires {
		reqStr[k.kind+"\x00"+k.selector+"\x00"+k.action] = v
	}
	composed := map[string]any{
		"requires": reqStr,
		"effects":  composeEffects(nodes),
		"bounds":   bounds,
	}
	res.Errors = append(res.Errors, reqErrs...)
	res.Errors = append(res.Errors, subsetViolations(requires, callerHolds)...)
	if pbRaw, has := doc["parent_bounds"]; has {
		if pb, ok := pbRaw.(map[string]any); ok {
			res.Errors = append(res.Errors, boundsViolations(bounds, pb, "graph")...)
			res.Errors = append(res.Errors, splitViolations(plan, nodes, pb)...)
			shares := leafAllotments(plan, pb)
			sharesAny := map[string]any{}
			for k, v := range shares {
				sharesAny[k] = v
			}
			composed["shares"] = sharesAny
		}
	}
	res.Composed = composed
	return res
}

// parentBoundsFiniteErrors mirrors Python bounds_errors: every amount must be a
// finite number, also for dicts built in code. NOTE (V22 4-lens n4): under the
// current wiring this is masked in BOTH implementations — the schema's integer
// type check rejects NaN/Inf before this runs, so the "not a finite" arm fires
// only for shapes the schema layer cannot see; it is kept as the faithful
// port of the oracle's (equally masked) bounds_errors.
func parentBoundsFiniteErrors(pb map[string]any) []string {
	var errs []string
	for _, name := range append(append([]string{}, summedBounds...), timeBound) {
		v, has := pb[name]
		if !has {
			continue
		}
		amount := v
		if name == "max_cost" {
			if m, ok := v.(map[string]any); ok {
				amount = m["amount"]
			}
		}
		if !isFiniteAmount(amount) {
			errs = append(errs, fmt.Sprintf("parent_bounds/%s: %v is not a finite number", name, amount))
		}
	}
	return errs
}

func isFiniteAmount(v any) bool {
	switch t := v.(type) {
	case int64:
		return true
	case int:
		return true
	case float64:
		return !math.IsNaN(t) && !math.IsInf(t, 0)
	}
	return false
}

// JSONableBounds converts int64 values to strings for printing (the printed value is the compared value).
func JSONableBounds(b map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range b {
		if k == "max_cost" {
			if cm, ok := v.(map[string]any); ok {
				out[k] = map[string]any{"amount": fmt.Sprintf("%d", cm["amount"]), "unit": cm["unit"]}
			}
		} else {
			out[k] = fmt.Sprintf("%d", v)
		}
	}
	return out
}
