"""Candidate-local, fail-closed correction of the exact upstream FSDP2 function."""
import ast as _compat_ast
import hashlib as _compat_hashlib
import inspect as _compat_inspect

# SHA256 of the exact diagnosed upstream function source.
_COMPAT_UPSTREAM_AST_SHA256 = '438b1857e20f35d9ddac6cafef07b4c39aba7db36fbb3b9b468c9696bec87e4d'

def install_fsdp2_set_compat(impl):
    original = impl.apply_fsdp2
    source = _compat_inspect.getsource(original)
    tree = _compat_ast.parse(source)
    node = tree.body[0]
    if len(tree.body) != 1 or not isinstance(node, _compat_ast.FunctionDef) or node.name != 'apply_fsdp2':
        raise RuntimeError('unexpected FSDP2 source shape')
    digest = _compat_hashlib.sha256(source.encode()).hexdigest()
    if digest != _COMPAT_UPSTREAM_AST_SHA256:
        raise RuntimeError('unreviewed upstream apply_fsdp2: ' + digest)
    replacement = _compat_ast.parse('assert fsdp_transformer_layer_cls_to_wrap and all(name is not None for name in fsdp_transformer_layer_cls_to_wrap)').body[0]
    matches = [i for i, stmt in enumerate(node.body) if isinstance(stmt, _compat_ast.Assert) and 'fsdp_transformer_layer_cls_to_wrap[0]' in _compat_ast.unparse(stmt)]
    if len(matches) != 1:
        raise RuntimeError('expected exactly one FSDP2 validation assertion')
    node.body[matches[0]] = _compat_ast.copy_location(replacement, node.body[matches[0]])
    _compat_ast.fix_missing_locations(tree)
    namespace = {}
    exec(compile(tree, _compat_inspect.getsourcefile(original) or '<fsdp2-compat>', 'exec'), original.__globals__, namespace)
    impl.apply_fsdp2 = namespace['apply_fsdp2']
    return impl.apply_fsdp2
