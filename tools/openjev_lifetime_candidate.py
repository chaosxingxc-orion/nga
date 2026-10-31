#!/usr/bin/env python3
"""Generate a bounded, Delete-only candidate from the frozen native GDN function.

No module import, model loading, allocation or NPU work occurs during generation.
The caller supplies the already loaded native function's trusted globals at build
 time. Numerical equivalence and memory improvement require a separate experiment.
"""
import ast
import copy
import functools
import hashlib
import inspect

SOURCE_SHA256 = '0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded'
FUNCTION = 'torch_chunk_gated_delta_rule'
VARIANTS = ('L1', 'L2', 'L1L2')


def tree_dump(node):
    return ast.dump(node, include_attributes=False)


def native_tree(source):
    if not isinstance(source, bytes) or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Frozen native source SHA256 differs')
    tree = ast.parse(source)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == FUNCTION]
    if len(funcs) != 1 or any(isinstance(n, ast.Delete) for n in ast.walk(funcs[0])):
        raise ValueError('Unexpected native function structure')
    return funcs[0]


def assigned_names(stmt):
    if not isinstance(stmt, ast.Assign):
        return ()
    return tuple(n.id for target in stmt.targets for n in ast.walk(target)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))


def delete(*names):
    return ast.Delete(targets=[ast.Name(id=n, ctx=ast.Del()) for n in names])


def candidate_tree(source, variant):
    """Only insert top-level Delete statements; all existing AST nodes stay intact."""
    if variant not in VARIANTS:
        raise ValueError('Unknown lifetime variant')
    original = native_tree(source)
    result = copy.deepcopy(original)
    body = []
    counts = dict(reshape=0, triangular=0, value=0, k_cumdecay=0, recurrent=0)
    for stmt in result.body:
        body.append(stmt)
        names = assigned_names(stmt)
        if names == ('query', 'key', 'value', 'k_beta', 'v_beta'):
            counts['reshape'] += 1
            if variant in ('L1', 'L1L2'):
                body.append(delete('value', 'beta'))
        elif isinstance(stmt, ast.For) and tree_dump(stmt.iter) == tree_dump(ast.parse('range(1, chunk_size)', mode='eval').body):
            counts['triangular'] += 1
            if variant in ('L1', 'L1L2'):
                body.append(delete('row', 'sub'))
        elif names == ('value',) and isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, ast.MatMult):
            counts['value'] += 1
            if variant in ('L1', 'L1L2'):
                body.append(delete('v_beta'))
        elif names == ('k_cumdecay',):
            counts['k_cumdecay'] += 1
            if variant in ('L1', 'L1L2'):
                body.append(delete('k_beta', 'attn'))
        elif isinstance(stmt, ast.For) and tree_dump(stmt.iter) == tree_dump(ast.parse('range(0, total_sequence_length // chunk_size)', mode='eval').body):
            counts['recurrent'] += 1
            if variant in ('L2', 'L1L2'):
                dead = ['query', 'key', 'value', 'k_cumdecay', 'decay_mask', 'g',
                        'q_i', 'k_i', 'v_i', 'v_prime', 'v_new', 'attn_inter', 'attn']
                if variant == 'L2':
                    dead += ['beta', 'row', 'sub', 'v_beta', 'k_beta']
                body.append(delete(*dead))
    if counts != dict.fromkeys(counts, 1):
        raise ValueError('Lifetime insertion anchors differ: ' + repr(counts))
    result.body = body
    stripped = copy.deepcopy(result)
    stripped.body = [s for s in stripped.body if not isinstance(s, ast.Delete)]
    if tree_dump(stripped) != tree_dump(original):
        raise ValueError('Candidate changed native arithmetic AST')
    ast.fix_missing_locations(result)
    return result


def generated_source(source, variant):
    return ast.unparse(candidate_tree(source, variant)) + '\n'


def validate_call(torch, bound):
    """Constrain the external wrapper without inserting guards into arithmetic."""
    a = bound.arguments
    if (type(a['chunk_size']) is not int or a['chunk_size'] != 64
            or a['initial_state'] is not None or a['output_final_state'] is not False
            or type(a['use_qk_l2norm_in_kernel']) is not bool
            or set(a['kwargs']) - {'cu_seqlens'}
            or a['kwargs'].get('cu_seqlens') is not None):
        raise ValueError('Only C64, no cache/final state, and native cu_seqlens=None supported')
    if not torch.is_inference_mode_enabled() or torch.is_grad_enabled():
        raise ValueError('Lifetime candidate requires inference_mode and disabled gradients')
    tensors = [a[k] for k in ('query', 'key', 'value', 'g', 'beta')]
    if any(not isinstance(t, torch.Tensor) or t.requires_grad for t in tensors):
        raise ValueError('Expected non-gradient tensors')
    q, k, v, g, beta = tensors
    if (q.ndim != 4 or q.shape != k.shape or q.shape != v.shape
            or any(type(n) is not int or n <= 0 for n in q.shape)
            or q.shape[-1] != 128 or q.shape[2] not in (16, 32)
            or tuple(g.shape) != tuple(q.shape[:3]) or beta.shape != g.shape
            or any(t.device != q.device for t in tensors)):
        raise ValueError('Expected nonempty native Qwen3.5 2B/9B GDN shapes')


def build_arithmetic(source, native_function, variant):
    """Compile only the verified function, using the supplied native globals.

    Loading/authenticating the native module and framework remains the run
    launcher's responsibility. This function neither imports nor executes the
    rest of the supplied source file.
    """
    original = native_tree(source)
    if native_function.__name__ != FUNCTION:
        raise ValueError('Wrong native function')
    actual = ast.parse(inspect.getsource(native_function)).body[0]
    if tree_dump(actual) != tree_dump(original):
        raise ValueError('Loaded native function differs from frozen source')
    if variant == 'original':
        return native_function
    tree = ast.Module(body=[candidate_tree(source, variant)], type_ignores=[])
    namespace = dict(native_function.__globals__)
    exec(compile(tree, '<openjev-lifetime-' + variant + '>', 'exec'), namespace)
    return namespace[FUNCTION]


def build_candidate(source, native_function, variant):
    """Standalone guarded API; runtime uses arithmetic under one common guard."""
    candidate = build_arithmetic(source, native_function, variant)
    namespace = native_function.__globals__
    signature = inspect.signature(native_function)
    @functools.wraps(native_function)
    def guarded(*args, **kwargs):
        bound = signature.bind(*args, **kwargs); bound.apply_defaults()
        validate_call(namespace['torch'], bound)
        return candidate(*bound.args, **bound.kwargs)
    guarded.lifetime_variant = variant
    guarded.native_source_sha256 = SOURCE_SHA256
    guarded.candidate_source_sha256 = hashlib.sha256(generated_source(source, variant).encode()).hexdigest()
    return guarded
