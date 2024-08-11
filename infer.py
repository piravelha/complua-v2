from typing import Dict, Tuple
from lark import Token
from dataclasses import is_dataclass
from type_models import *
from util import get_loc, unify, filter_dependencies
import re

def get_path(path, **kw):
  def run(path, env):
    if isinstance(path, Token):
      return env[path], env
    if path.data == "prop_expr":
      prefix, prop = path.children
      prefix, _ = run(prefix, env)
      if isinstance(prefix, str): return prefix, _
      assert isinstance(prefix, TableType)
      return run(prop, prefix.fields)[0], prefix
    if path.data == "index_expr":
      prefix, _ = path.children
      prefix, _ = run(prefix, env)
      if isinstance(prefix, str): return prefix, _
      assert isinstance(prefix, DictType)
      return prefix.value, prefix
    assert False
  def get_right(path):
    if isinstance(path, Token):
      return path
    return get_right(path.children[1])
  value, parent = run(path, kw["env"])
  if isinstance(value, str): return value
  return get_right(path), parent

def infer_NAME(value, **kw) -> 'AnyType | str':
  if kw["env"].get(value):
    type = kw["env"][value]
    type.dependencies += [value]
    return type
  return UnknownType([value], False, kw["loc"])

def infer_NUMBER(value, **kw) -> 'AnyType | str':
  return NumberType([], kw["loc"])

def infer_STRING(value, **kw) -> 'AnyType | str':
  return StringType([], kw["loc"])

def infer_template_literal(_, *contents, **kw):
  for content in contents:
    x, _ = content.children
    x = infer(x, **kw)
    if isinstance(x, str):
      return x
  return StringType()

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
    if isinstance(value, TupleType):
      value = value.values[0]
    if isinstance(value, str): return value
    new_fields[key.value] = value
    deps += value.dependencies
  return TableType(new_fields, deps, False, kw["loc"])

def infer_dict(*fields, **kw):
  key_type = None
  value_type = None
  for field in fields:
    if len(field.children) == 2:
      key, value = field.children
      key = infer(key, **kw)
    else:
      value = field.children[0]
      key = NumberType()
    if isinstance(key, str): return key
    value = infer(value, **kw)
    if isinstance(value, str): return value 
    if isinstance(key, TupleType):
      key = key.values[0]
    if isinstance(value, TupleType):
      value = value.values[0]
    if not key_type:
      key_type = key
    if not value_type:
      value_type = value
    k = unify(key_type, key)
    if isinstance(k, str): return k
    key_type = k
    v = unify(value_type, value)
    if isinstance(v, str): return v
    value_type = v
  assert key_type
  assert value_type
  return DictType(key_type, value_type, key_type.dependencies + value_type.dependencies, False, kw["loc"])

def infer_prop_expr(prefix, prop, **kw) -> 'AnyType | str':
  prefix_type = infer(prefix, **kw)
  if isinstance(prefix_type, TupleType):
    prefix_type = prefix_type.values[0]
  if isinstance(prefix_type, str): return prefix_type
  if isinstance(prefix_type, UnknownType):
    return prefix_type
  if not isinstance(prefix_type, TableType):
    return f"???:{kw['loc']}: Attempting to access property '{prop}' on a non-table value '{prefix_type}'"
  for key, value in prefix_type.fields.items():
    if key == prop.value:
      return value
  return f"???:{kw['loc']}: Property '{prop}' does not exist on table '{prefix_type}'"

def infer_index_expr(prefix, index, **kw):
  prefix_type = infer(prefix, **kw)
  if isinstance(prefix_type, str): return prefix_type
  if isinstance(prefix_type, TupleType):
    prefix_type = prefix_type.values[0]
  index_type = infer(index, **kw)
  if isinstance(index_type, str): return index_type
  if isinstance(index_type, TupleType):
    index_type = index_type.values[0]
  if isinstance(prefix_type, UnknownType):
    prefix_type.dependencies += index_type.dependencies
    return prefix_type
  if not isinstance(prefix_type, DictType):
    return f"???:{kw['loc']}: Attempting to index a non-dictionary type: '{prefix_type}'"
  u = unify(prefix_type.key, index_type)
  if isinstance(u, str): return u
  return prefix_type.value


def infer_unary_expr(op, expr, **kw) -> 'AnyType | str':
  expr_type = infer(expr, **kw)
  if isinstance(expr_type, str): return expr_type
  if op == "not":
    t1 = unify(expr_type, BooleanType())
    if isinstance(t1, str): return t1
    return BooleanType(t1.dependencies)
  if op == "-":
    t1 = unify(expr_type, NumberType())
    if isinstance(t1, str): return t1
    return NumberType(t1.dependencies)
  if op == "#":
    t1 = unify(expr_type, StringType())
    if isinstance(t1, str):
      if isinstance(expr_type, (TableType, DictType)):
        return NumberType(expr_type.dependencies)
      return t1
    return NumberType(t1.dependencies)
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
  return NumberType(t1.dependencies + t2.dependencies)

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
    return StringType(t1.dependencies + t2.dependencies)
  else:
    t1 = unify(left_type, NumberType())
    if isinstance(t1, str): return t1
    t2 = unify(right_type, NumberType())
    if isinstance(t2, str): return t2
    return NumberType(t1.dependencies + t2.dependencies)

def infer_rel_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left_type
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right_type
  t1 = unify(left_type, NumberType())
  if isinstance(t1, str): return t1
  t2 = unify(right_type, NumberType())
  if isinstance(t2, str): return t2
  return BooleanType(t1.dependencies + t2.dependencies)


def infer_eq_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left_type
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right_type
  t1 = unify(left_type, right_type)
  if isinstance(t1, str): return t1
  return BooleanType(t1.dependencies)

def infer_log_expr(left, op, right, **kw) -> 'AnyType | str':
  left_type = infer(left, **kw)
  if isinstance(left_type, str): return left_type
  right_type = infer(right, **kw)
  if isinstance(right_type, str): return right_type
  t1 = unify(left_type, BooleanType())
  if isinstance(t1, str): return t1
  t2 = unify(right_type, BooleanType())
  if isinstance(t2, str): return t2
  return BooleanType(t1.dependencies + t2.dependencies)

infer_and_expr = infer_log_expr
infer_or_expr = infer_log_expr



def infer_func_body(params, body, **kw) -> 'AnyType | str':
  kw["env"] = kw["env"].copy()
  for param in params.children:
    kw["env"][param.value] = UnknownType([], True, kw["loc"])
  body_type = infer(body, **kw)
  if isinstance(body_type, str): return body_type
  assert isinstance(body_type, TupleType)
  return FunctionType(body_type, kw["this"], None, body_type.dependencies, False, False, kw["loc"])

def infer_func_expr(func, **kw) -> 'AnyType | str':
  return infer(func, **kw)

def infer_func_call(prefix, args, **kw) -> 'AnyType | str':
  prefix_type = infer(prefix, **kw)
  if isinstance(prefix_type, str):
    return prefix_type
  prefix_depens = prefix_type.dependencies.copy()
  new_args = []
  arg_depens = []
  for arg in args.children:
    arg = infer(arg, **kw)
    if isinstance(arg, str):
      return arg
    if isinstance(arg, TupleType):
      new_args.extend(arg.values)
      arg_depens.extend(arg.dependencies)
    else:
      new_args.append(arg)
      arg_depens.extend(arg.dependencies)
  if isinstance(prefix_type, TupleType):
    prefix_type = prefix_type.values[0] if prefix_type.values else NilType()
  if isinstance(prefix_type, UnknownType):
    prefix_depens += arg_depens
    prefix_type.dependencies += prefix_depens
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
  kw["env"] = kw["env"].copy()
  for param, arg in zip(params.children, new_args):
    assert isinstance(param, Token)
    arg = arg.copy()
    arg.is_parameter = True
    kw["env"][param.value] = arg
  results = infer(body, **kw)
  if isinstance(results, str):
    return results
  assert isinstance(results, TupleType)
  deps = prefix_depens + arg_depens
  results.dependencies += deps
  return results

def infer_call_stmt(call, **kw) -> 'AnyType | str':
  return infer(call, **kw)

def infer_func_decl(name, func, **kw) -> 'AnyType | str':
  kw["env"][name.value] = UnknownType([], False, kw["loc"])
  func = infer(func, **kw)
  if isinstance(func, str): return func
  assert isinstance(func, FunctionType)
  func = func.copy()
  if kw["checkcall"].get(name.value):
    func.checkcall = kw["checkcall"][name.value]
  func.dependencies += [name]
  kw["env"][name.value] = func
  return NilType([], kw["loc"])

infer_local_func_decl = infer_func_decl

def infer_var_decl(names, exprs, **kw) -> 'AnyType | str':
  new_exprs: list[Type] = []
  for expr in exprs.children:
    expr = infer(expr, **kw)
    if isinstance(expr, str): return expr
    if isinstance(expr, TupleType):
      for val in expr.values:
        val.dependencies = expr.dependencies
        new_exprs.append(val)
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

def infer_assign_stmt(prefix, expr, **kw):
  expr = infer(expr, **kw)
  if isinstance(expr, str): return expr
  if isinstance(expr, TupleType):
    expr = expr.values[0]
  result = get_path(prefix, **kw)
  if isinstance(result, str): return result
  last, parent = result
  if isinstance(parent, DictType):
    u = unify(expr, parent.key)
    if isinstance(u, str): return u
    return NilType()
  if isinstance(parent, TableType):
    if last.value not in parent.fields:
      parent.fields[last.value] = expr
      return NilType()
    u = unify(expr, parent.fields[last.value])
    if isinstance(u, str): return u
  if isinstance(parent, dict):
    if not parent.get(last.value):
      parent[last.value] = expr
      return NilType()
    u = unify(expr, parent[last.value])
    if isinstance(u, str): return u
  return NilType()

def infer_if_stmt(cond, body, elif_bs, else_b, **kw):
  cond = infer(cond, **kw)
  if isinstance(cond, str): return cond
  if isinstance(cond, TupleType): cond = cond.values[0] if cond.values else NilType()
  c = unify(cond, BooleanType())
  if isinstance(c, str): return c
  body = infer(body, **kw)
  assert isinstance(body, TupleType)
  for elif_b in elif_bs.children:
    elif_cond, elif_body = elif_b.children
    elif_cond = infer(elif_cond, **kw)
    if isinstance(elif_cond, str): return cond
    if isinstance(elif_cond, TupleType): elif_cond = elif_cond.values[0] if elif_cond.values else NilType()
    c = unify(cond, BooleanType())
    if isinstance(c, str): return c
    elif_body = infer(elif_body, **kw)
    assert isinstance(elif_body, TupleType)
    new = []
    for a, b in zip(body.values, elif_body.values):
      x = unify(a, b)
      if isinstance(x, str): return x
      new.append(x)
    body = TupleType(new, body.dependencies + elif_body.dependencies)
  if else_b:
    else_body = else_b.children[0]
    else_body = infer(else_body, **kw)
    assert isinstance(else_body, TupleType)
    new = []
    for a, b in zip(body.values, else_body.values):
      x = unify(a, b)
      if isinstance(x, str): return x
      new.append(x)
    body = TupleType(new, body.dependencies + else_body.dependencies)
  return body

def infer_range_for_stmt(var, e1, e2, e3, body, **kw):
  e1 = infer(e1, **kw)
  if isinstance(e1, str): return e1
  t1 = unify(e1, NumberType())
  if isinstance(t1, str): return t1
  if e2:
    e2 = infer(e2, **kw)
    if isinstance(e2, str): return e2
    t2 = unify(e2, NumberType())
    if isinstance(t2, str): return t2
    if e3:
      e3 = infer(e3, **kw)
      if isinstance(e3, str): return e3
      t3 = unify(e3, NumberType())
      if isinstance(t3, str): return t3
  kw["env"] = kw["env"].copy()
  kw["env"][var.value] = NumberType()
  return infer(body, **kw)

def infer_iter_for_stmt(names, expr, body, **kw):
  iter = infer(expr, **kw)
  if isinstance(iter, str): return iter
  if isinstance(iter, TupleType): iter = iter.values[0]
  if isinstance(iter, UnknownType):
    body = infer(body, **kw)
    if isinstance(body, str): return body
    body.dependencies += iter.dependencies
    return body
  if not isinstance(iter, FunctionType):
    return f"???:{kw['loc']}: Attempting to iterate with '{iter}', expected an iterator function"
  kw["env"] = kw["env"]
  for n, e in zip(names.children, iter.returns.values):
    kw["env"][n.value] = e
  return infer(body, **kw)

def infer_of_for_stmt(name, expr, body, **kw):
  expr = infer(expr, **kw)
  if isinstance(expr, str): return expr
  if isinstance(expr, TupleType): expr = expr.values[0]
  if isinstance(expr, UnknownType):
    body = infer(body, **kw)
    if isinstance(body, str): return body
    body.dependencies += expr.dependencies
    return body
  if not isinstance(expr, DictType):
    return f"???:{kw['loc']}: Attempting to iterate over a non-dictionary type: '{expr}'"
  kw["env"] = kw["env"].copy()
  kw["env"][name.value] = expr
  return infer(body, **kw)

def infer_it_for_stmt(expr, body, **kw):
  expr = infer(expr, **kw)
  if isinstance(expr, str): return expr
  if isinstance(expr, TupleType): expr = expr.values[0]
  if isinstance(expr, UnknownType):
    body = infer(body, **kw)
    if isinstance(body, str): return body
    body.dependencies += expr.dependencies
    return body
  if not isinstance(expr, DictType):
    return f"???:{kw['loc']}: Attempting to iterate over a non-dictionary type: '{expr}'"
  kw["env"] = kw["env"].copy()
  kw["env"]["it"] = expr.value
  kw["env"]["idx"] = NumberType()
  return infer(body, **kw)



def infer_return_stmt(exprs, **kw) -> 'AnyType | str':
  if not exprs:
    return TupleType([])
  new_exprs = TupleType([])
  for expr in exprs.children:
    expr = infer(expr, **kw)
    if isinstance(expr, str): return expr
    if isinstance(expr, TupleType):
      new_exprs.values.extend(expr.values)
    else:
      new_exprs.values.append(expr)
  return new_exprs

def infer_eval(expr, **kw) -> 'AnyType | str':
  return infer(expr, **kw)

def infer_checkcall(name, func, **kw) -> 'AnyType | str':
  kw["checkcall"][name.value] = func
  return NilType([], kw["loc"])

def infer_inline(func_decl, **kw) -> 'AnyType | str':
  name, func = func_decl.children
  func = infer(func, **kw)
  if isinstance(func, str): return func
  assert isinstance(func, FunctionType)
  if kw["checkcall"].get(name.value):
    func.checkcall = kw["checkcall"][name.value]
  func.inline = True
  kw["env"][name.value] = func
  return NilType([], kw["loc"])

def infer_using(*names, **kw):
  return NilType()

def infer_chunk(*stmts, **kw) -> 'AnyType | str':
  *stmts, last = stmts
  returns = []
  depens = []
  for stmt in stmts:
    stmt = infer(stmt, **kw)
    if isinstance(stmt, str):
      return stmt
    if isinstance(stmt, TupleType):
      for i, ret in enumerate(stmt.values):
        if i >= len(returns): returns.append(ret)
        else: returns[i] = unify(returns[i], ret)
        if isinstance(returns[i], str): return returns[i]
    depens.extend(stmt.dependencies)

  last = last and infer(last, **kw) or TupleType([])
  if isinstance(last, str): return last
  assert isinstance(last, TupleType)
  for i, ret in enumerate(last.values):
    if i >= len(returns): returns.append(ret)
    else: returns[i] = unify(returns[i], ret)
    if isinstance(returns[i], str): return returns[i]
  depens.extend(last.dependencies)
  rets = TupleType(returns)
  new_depens = []
  for dep in depens:
    found = False
    if v := kw["env"].get(str(dep)):
      if v.is_parameter:
        found = True
        break
    if not found:
      new_depens.append(dep)
  rets.dependencies = new_depens
  return rets

def infer(tree, **kw) -> 'AnyType | str':
  kw["this"] = tree
  kw["loc"] = get_loc(tree)
  if isinstance(tree, Token):
    return globals()["infer_" + tree.type](tree.value, **kw)
  return globals()["infer_" + tree.data](*tree.children, **kw)
