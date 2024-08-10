from lark import Token
from type_models import *
from parser import parser
from util import get_loc, unify, filter_dependencies

def infer_NAME(value, **kw) -> 'AnyType | str':
  if kw["env"].get(value):
    type = kw["env"][value]
    type.dependencies = type.dependencies + [kw["this"]]
    return type
  return UnknownType([], kw["loc"])

def infer_NUMBER(value, **kw) -> 'AnyType | str':
  return NumberType([], kw["loc"])

def infer_STRING(value, **kw) -> 'AnyType | str':
  return StringType([], kw["loc"])

def infer_BOOLEAN(value, **kw) -> 'AnyType | str':
  return BooleanType([], kw["loc"])

def infer_NIL(value, **kw) -> 'AnyType | str':
  return NilType([], kw["loc"])

def infer_paren(expr, **kw) -> 'AnyType | str':
  return infer(expr, **kw)

def infer_table(*fields, **kw) -> 'AnyType | str':
  new_fields = {}
  deps = []
  for field in fields:
    key, value = field.children
    value = infer(value, **kw)
    if isinstance(value, list):
      value = value[0]
    if isinstance(value, str): return value
    new_fields[key] = value
    deps += value.dependencies
  return TableType(new_fields, deps, kw["loc"])

def infer_prop_expr(prefix, prop, **kw) -> 'AnyType | str':
  prefix_type = infer(prefix, **kw)
  if isinstance(prefix_type, list):
    prefix_type = prefix_type[0]
  if isinstance(prefix_type, str): return prefix_type
  if isinstance(prefix_type, UnknownType):
    return prefix_type
  if not isinstance(prefix_type, TableType):
    return f"???:{kw['loc']}: Attempting to access property '{prop}' on a non-table value '{prefix_type}'"
  for key, value in prefix_type.fields.items():
    if key == prop.value:
      return value
  return f"???:{kw['loc']}: Property '{prop}' does not exist on table '{prefix_type}'"

def infer_unary_expr(op, expr, **kw) -> 'AnyType | str':
  expr_type = infer(expr, **kw)
  if isinstance(expr_type, str): return expr_type
  if op == "not":
    t1 = unify(expr_type, BooleanType())
    if isinstance(t1, str): return t1
    return BooleanType([expr] + t1.dependencies)
  if op == "-":
    t1 = unify(expr_type, NumberType())
    if isinstance(t1, str): return t1
    return NumberType([expr] + t1.dependencies)
  if op == "#":
    t1 = unify(expr_type, StringType())
    if isinstance(t1, str):
      if isinstance(expr_type, TableType):
        return NumberType([expr] + expr_type.dependencies)
      return t1
    return NumberType([expr] + t1.dependencies)
  assert False, f"Not implemented: {op}"

def infer_math_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left_type
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right_type
  t1 = unify(left_type, NumberType())
  if isinstance(t1, str): return t1
  t2 = unify(right_type, NumberType())
  if isinstance(t2, str): return t2
  return NumberType(t1.dependencies + t2.dependencies + [left] + [right])

infer_pow_expr = infer_math_expr
infer_mul_expr = infer_math_expr

def infer_add_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right
  if op == "..":
    t1 = unify(left_type, StringType())
    if isinstance(t1, str): return t1
    t2 = unify(right_type, StringType())
    if isinstance(t2, str): return t2
    return StringType(t1.dependencies + t2.dependencies + [left] + [right])
  else:
    t1 = unify(left_type, NumberType())
    if isinstance(t1, str): return t1
    t2 = unify(right_type, NumberType())
    if isinstance(t2, str): return t2
    return NumberType(t1.dependencies + t2.dependencies + [left] + [right])

def infer_eq_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left_type
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right_type
  t1 = unify(left_type, right_type)
  if isinstance(t1, str): return t1
  return BooleanType(t1.dependencies + [left] + [right])

def infer_func_body(params, body, **kw) -> 'AnyType | str':
  kw["env"] = kw["env"].copy()
  for param in params.children:
    kw["env"][param.value] = UnknownType([], kw["loc"])
  body_type = infer(body, **kw)
  assert isinstance(body_type, list)
  deps = [d for ret in body_type for d in ret.dependencies] + [body]
  new_deps = []
  for dep in deps:
    equals = False
    for param in params.children:
      if dep == param:
        equals = True
        break
    if not equals: new_deps.append(dep)
  if isinstance(body_type, str): return body_type
  return FunctionType(body_type, kw["this"], None, new_deps, False, kw["loc"])

def infer_func_expr(func, **kw) -> 'AnyType | str':
  return infer(func, **kw)

def infer_func_call(prefix, args, **kw) -> 'AnyType | str':
  prefix_type = infer(prefix, **kw)
  if isinstance(prefix_type, str): return prefix_type
  new_args = []
  for arg in args.children:
    arg = infer(arg, **kw)
    if isinstance(arg, list):
      arg = arg[0]
    if isinstance(arg, str): return arg
    new_args.append(arg)
  if isinstance(prefix_type, list):
    prefix_type = prefix_type[0]
  if isinstance(prefix_type, UnknownType):
    prefix_type.dependencies += [d for arg in new_args for d in arg.dependencies]
    return prefix_type
  if not isinstance(prefix_type, FunctionType):
    return f"???:{kw['loc']}: Attempting to call a non-function value of type '{prefix_type}'"
  params, body = prefix_type.tree.children
  if len(new_args) < len(params.children):
    return f"???:{kw['loc']}: Not enough arguments provided to function '{prefix_type}', " \
      + f"expected {len(params.children)}, but got {len(new_args)}"
  if len(new_args) > len(params.children):
    return f"???:{kw['loc']}: Too many arguments provided to function '{prefix_type}', " \
      + f"expected {len(params.children)}, but got {len(new_args)}"
  for param, arg in zip(params.children, new_args):
    assert isinstance(param, Token)
    kw["env"][param.value] = arg
  results = infer(body, **kw)
  if isinstance(results, str): return results
  assert isinstance(results, list)
  deps = [prefix] + args.children
  deps += [d for arg in new_args for d in arg.dependencies] + prefix_type.dependencies
  for result in results:
    result.dependencies += deps
  return results

def infer_call_stmt(call, **kw) -> 'AnyType | str':
  return infer(call, **kw)

def infer_func_decl(name, func, **kw) -> 'AnyType | str':
  func = infer(func, **kw)
  if isinstance(func, str): return func
  assert isinstance(func, FunctionType)
  if kw["checkcall"].get(name.value):
    func.checkcall = kw["checkcall"][name.value]
  kw["env"][name.value] = func
  return NilType(kw["loc"])

def infer_var_decl(names, exprs, **kw) -> 'AnyType | str':
  new_exprs: list[Type] = []
  for expr in exprs.children:
    expr = infer(expr, **kw)
    if isinstance(expr, str): return expr
    if isinstance(expr, list):
      new_exprs.extend(expr)
    else:
      new_exprs.append(expr)
  if len(new_exprs) < len(names.children):
    return f"???:{kw['loc']}: Not enough expressions provided on variable declaration, " \
      + f"expected '{len(names.children)}', but got '{len(new_exprs)}'"
  if len(new_exprs) > len(names.children):
    return f"???:{kw['loc']}: Too many expressions provided on variable declaration, " \
      + f"expected '{len(names.children)}', but got '{len(new_exprs)}'"
  for name, expr in zip(names.children, new_exprs):
    kw["env"][name.value] = expr
  return NilType([], kw["loc"])

def infer_return_stmt(exprs, **kw) -> 'AnyType | str':
  if not exprs:
    return []
  new_exprs = []
  for expr in exprs.children:
    expr = infer(expr, **kw)
    if isinstance(expr, str): return expr
    if isinstance(expr, list):
      new_exprs.extend(expr)
    else:
      new_exprs.append(expr)
  return new_exprs

def infer_eval(expr, **kw) -> 'AnyType | str':
  return infer(expr, **kw)

def infer_checkcall(name, func, **kw) -> 'AnyType | str':
  kw["checkcall"][name.value] = func
  return NilType(kw["loc"])

def infer_inline(func_decl, **kw) -> 'AnyType | str':
  name, func = func_decl.children
  func = infer(func, **kw)
  if isinstance(func, str): return func
  assert isinstance(func, FunctionType)
  if kw["checkcall"].get(name.value):
    func.checkcall = kw["checkcall"][name.value]
  func.inline = True
  kw["env"][name.value] = func
  return NilType(kw["loc"])

def infer_chunk(*stmts, **kw) -> 'AnyType | str':
  *stmts, last = stmts
  returns = []
  for stmt in stmts:
    stmt = infer(stmt, **kw)
    if isinstance(stmt, str): return stmt
    if isinstance(stmt, list):
      for i, ret in enumerate(stmt):
        if i >= len(returns): returns.append(ret)
        else: returns[i] = unify(returns[i], ret)
        if isinstance(returns[i], str): return returns[i]
  last = last and infer(last, **kw) or []
  if isinstance(last, str): return last
  assert isinstance(last, list)
  for i, ret in enumerate(last):
    if i >= len(returns): returns.append(ret)
    else: returns[i] = unify(returns[i], ret)
    if isinstance(returns[i], str): return returns[i]
  return returns

def infer(tree, **kw) -> 'AnyType | str':
  kw["this"] = tree
  kw["loc"] = get_loc(tree)
  if isinstance(tree, Token):
    return globals()["infer_" + tree.type](tree.value, **kw)
  return globals()["infer_" + tree.data](*tree.children, **kw)
