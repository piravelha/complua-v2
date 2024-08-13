#!/usr/bin/python
import os
import subprocess
import sys
from lark import Token, Tree
from parser import parser, any_parser
from type_models import *
from util import get_loc, get_dependencies, replace_name
from infer import *
from formatter import format
from builtin_types import types

PATH = os.path.dirname(os.path.abspath(__file__))

def get_using(path, name, current=None, acc="", **kw):
  if current is None:
    current = kw["type_env"]
  if name in kw["env"]:
    return name
  first, *rest = path
  type = current[first.value]
  if not rest:
    if name in type.fields:
      return f"{acc}{first}.{name}"
    return name
  return get_using(rest, name, type.fields, first + "." + acc, **kw)

def infer_from_compile(tree, **kw):
  if isinstance(tree, Token) and not globals().get("infer_"+tree.type):
    return tree
  if isinstance(tree, Tree) and not globals().get("infer_"+tree.data):
    return tree
  result = infer(tree, env=kw["type_env"], value_env=kw["env"], checkcall=kw["checkcall"], using=kw["using"], file=kw["file"], defer=kw["defer"], depens=kw["depens"])
  if isinstance(result, str):
    print(result)
    exit(1)
  return result

def compile_NAME(value, **kw) -> str:
  for using_path in kw["using"]:
    name = get_using(using_path, value, **kw)
    if name != value: return name
  return value

def compile_RAW_NAME(value, **kw) -> str:
  return value
 
def compile_NUMBER(value, **kw) -> str:
  return value

def compile_STRING(value, **kw) -> str:
  return value

def compile_template_literal(start, *contents, **kw):
  if start is None: start = ""
  s = str(start)
  vs = []
  for content in contents:
    x, r = content.children
    if r is None: r = ""
    s += "%s" + str(r)
    x = compile(x, **kw)
    vs.append(x)
  vs = "".join(f", {v}" for v in vs)
  return f"string.format(\"{s}\"{vs})"

def compile_BOOLEAN(value, **kw) -> str:
  return value

def compile_NIL(value, **kw) -> str:
  return value

def compile_paren(expr, **kw) -> str:
  return "(" + compile(expr, **kw) + ")"

def compile_table(*fields, **kw) -> str:
  code = "{\n"
  for field in fields:
    if field.data == "checkcall": continue
    key, value = field.children
    value = compile(value, **kw)
    code += f"{key} = {value},\n"
  return code + "}"

def compile_named_table(name, table, **kw):
  s = compile(table, **kw)[1:]
  s = f"{{\n[\"#NAME\"] = \"{name}\",\n" + s
  return s

def compile_dict(*fields, **kw):
  code = "{\n"
  for field in fields:
    if len(field.children) == 2:
      key, value = field.children
    else:
      value = field.children[0]
      key = None
    value = compile(value, **kw)
    if key:
      code += f"[{key}] = {value},\n"
    else:
      code += f"{value},\n"
  return code + "}"

def compile_prop_expr(prefix, prop, **kw) -> str:
  prefix = compile(prefix, **kw)
  return f"{prefix}.{prop.value}"

def compile_index_expr(prefix, index, **kw):
  prefix = compile(prefix, **kw)
  index = compile(index, **kw)
  return f"{prefix}[{index}]"

def compile_unary_expr(op, expr, **kw) -> str:
  expr = compile(expr, **kw)
  return f"{op} {expr}"

def compile_math_expr(left, op, right, **kw) -> str:
  left = compile(left, **kw)
  right = compile(right, **kw)
  return f"{left} {op} {right}"

compile_pow_expr = compile_math_expr
compile_mul_expr = compile_math_expr
compile_add_expr = compile_math_expr
compile_rel_expr = compile_math_expr
compile_eq_expr = compile_math_expr
compile_and_expr = compile_math_expr
compile_or_expr = compile_math_expr

def copy_kw(kw):
  kw["env"] = kw["env"].copy()
  return kw

def compile_default_param(param, expr, **kw):
  return param.value + "#" + compile(expr, **kw)

def compile_mutable_param(param, **kw):
  return compile(param, **kw)

def compile_func_body(params, body, **kw) -> str:
  kw = copy_kw(kw)
  body = compile(body, **kw)
  new_params = []
  defaults = []
  for param in params.children:
    param = compile(param, **kw)
    if "#" in param:
      p, d = param.split("#", 1)
      new_params.append(p)
      defaults.append(f"if {p} == nil then\n{p} = {d}\nend")
    else:
      new_params.append(param)
  params = ", ".join(new_params)
  defaults = "\n".join(defaults)
  return f"({params})\n{defaults}\n{body}\nend"

def compile_func_expr(func, **kw) -> str:
  return "function" + compile(func, **kw)

def compile_do_expr(chunk, **kw) -> str:
  chunk = compile(chunk, **kw)
  return f"(function()\n{chunk}\nend)()"

def compile_func_call(prefix, args, **kw) -> str:
  prefix_type = infer_from_compile(prefix, **kw)
  #prefix_type = infer(prefix, env=kw["type_env"], checkcall=kw["checkcall"], value_env=kw["env"], using=kw["using"])
  if isinstance(prefix_type, TupleType):
    prefix_type = prefix_type.values[0]
  prefix = compile(prefix, **kw)
  if isinstance(prefix_type, FunctionType):
    if prefix_type.inline:
      params, body = prefix_type.tree.children
      for p, a in zip(params.children, args.children):
        assert isinstance(p, Token)
        body = replace_name(body, p.value, a)
      return f"(function()\n" + compile(body, **kw) + "\nend)()"
  args = ", ".join(compile(a, **kw) for a in args.children)
  return f"{prefix}({args})"

def compile_call_stmt(call, **kw) -> str:
  return compile(call, **kw) + ";"

def compile_method_expr(prefix, name, args, **kw):
  return compile_func_call(
    Tree("prop_expr", [
      prefix,
      name,
    ]),
    Tree("args", [prefix] + args.children),
    **kw,
  )

def compile_method_stmt(call, **kw) -> str:
  return compile(call, **kw) + ";"


def compile_func_decl(name, func, **kw) -> str:
  kw["env"][name.value] = kw["this"]
  func = compile(func, **kw)
  return f"local function {name}{func}"

def compile_struct_decl(name, params, body, **kw):
  kw["env"][name.value] = kw["this"]
  params = ", ".join(str(p) for p in params.children)
  body = compile(Tree("table", body.children), **kw)
  return f"function {name}({params})\nreturn {body}\nend"

def compile_var_decl(names, exprs, **kw) -> str:
  for name, expr in zip(names.children, exprs.children):
    if name.value in kw["env"]:
      del kw["env"][name.value]
    kw["value_env"][name.value] = expr

  names = ", ".join(compile(n, **kw) for n in names.children)
  exprs = ", ".join(compile(e, **kw) for e in exprs.children)
  return f"local {names} = {exprs};"

def compile_const_decl(name, expr, **kw):
  kw["env"][name.value] = Tree("const_decl", [name, expr])
  kw["value_env"] = expr
  expr = compile(expr, **kw)
  return f"local {name} = {expr};"

def compile_assign_stmt(prefix, expr, **kw):
  prefix = compile(prefix, **kw)
  expr = compile(expr, **kw)
  return f"{prefix} = {expr};"

def compile_if_stmt(cond, body, elseif_bs, else_b, **kw):
  cond = compile(cond, **kw)
  body = compile(body, **kw)
  s = f"if {cond} then\n{body}\n"
  for elseif_b in elseif_bs.children:
    elseif_cond, elseif_body = elseif_b.children
    elseif_cond = compile(elseif_cond, **kw)
    elseif_body = compile(elseif_body, **kw)
    s += f"elseif {elseif_cond} then\n{elseif_body}\n"
  if else_b:
    else_body = else_b.children[0]
    else_body = compile(else_body, **kw)
    s += f"else\n{else_body}\n"
  return s + "end"

def compile_range_for_stmt(var, e1, e2, e3, body, **kw):
  if not e2:
    stop = compile(e1, **kw)
    start, step = "1", "1"
  elif not e3:
    start = compile(e1, **kw)
    stop = compile(e2, **kw)
    step = "1"
  else:
    start = compile(e1, **kw)
    stop = compile(e2, **kw)
    step = compile(e3, **kw)
  body = compile(body, **kw)
  return f"for {var} = {start}, {stop}, {step} do\n{body}\nend"

def compile_iter_for_stmt(names, iter, body, **kw):
  names = ", ".join(n.value for n in names.children)
  iter = compile(iter, **kw)
  body = compile(body, **kw)
  return f"for {names} in {iter} do\n{body}\nend"

def compile_of_for_stmt(name, expr, body, **kw):
  expr = compile(expr, **kw)
  body = compile(body, **kw)
  return f"for _, {name} in pairs({expr}) do\n{body}\nend"

def compile_it_for_stmt(expr, body, **kw):
  expr = compile(expr, **kw)
  body = compile(body, **kw)
  return f"for idx, it in pairs({expr}) do\n{body}\nend"



def compile_return_stmt(exprs, **kw) -> str:
  if not exprs:
    exprs = ""
  else:
    exprs = ", ".join(compile(e, **kw) for e in exprs.children)
  defers = "\n".join([compile(defer, **kw) for defer in kw["defer"]])
  return f"{defers}\nreturn {exprs};"

def compile_eval(expr, **kw) -> str:
  old_expr = expr
  path = "./.complua/.eval"
  expr = compile(expr, **kw)
  code = f"\n\nlocal __eval = {{ {expr} }};\n"
  code += f"file:write(_G['#COMPLUA'].serialize(__eval));\n"
  code += f"file:close();\n"
  with open(PATH+"/lib.lua") as f:
    lib = f.read()
  deps = get_dependencies(old_expr, **kw)
  with open(path, "w") as f:
    f.write(lib + "\n".join(deps) + code)
  out = subprocess.run(["luajit", path], stderr=subprocess.PIPE)
  if out.stderr:
    print(out.stderr.decode())
    exit(1)
  with open(path + ".temp", "r") as f:
    generated = f.read()
  return f"unpack({generated})"

def compile_load(expr, **kw) -> str:
  old_expr = expr
  path = "./.complua/.eval"
  expr = compile(expr, **kw)
  code = f"\n\nlocal __eval = {expr};\n"
  code += f"file:write(_G['#COMPLUA'].serialize(__eval));\n"
  code += f"file:close();\n"
  with open(PATH+"/lib.lua") as f:
    lib = f.read()
  deps = get_dependencies(old_expr, **kw)
  with open(path, "w") as f:
    f.write(lib + "\n".join(deps) + code)
  out = subprocess.run(["luajit", path], stderr=subprocess.PIPE)
  if out.stderr:
    print(out.stderr.decode())
    exit(1)
  with open(path + ".temp", "r") as f:
    generated = f.read()
  if generated[0] != "\"" or generated[-1] != "\"":
    print(f"{kw['file']}:{kw['loc']} Attempting to call '#load' directive with a non-string argument")
    exit(1)
  s = eval(generated)
  tree = any_parser.parse(s)
  type = infer_from_compile(tree, **kw)
  if isinstance(type, str):
    print(type)
    exit(1)
  return compile(tree, **kw)

def compile_inline(func_decl, **kw) -> str:
  return ""

def compile_defer(stmt, **kw):
  kw["defer"].append(stmt)
  return ""

def compile_checkcall(name, body, **kw) -> str:
  return ""

def compile_repr(expr, **kw):
  return compile_eval(Tree("func_call", [
    Tree("prop_expr", [
      Tree("index_expr", [
        Token("NAME", "_G"),
        Token("STRING", "\"#COMPLUA\""),
      ]),
      Token("RAW_NAME", "serialize"),
    ]),
    Tree("args", [expr])
  ]), **kw)

def compile_using(*names, **kw):
  kw["using"].append(names)
  return ""

def compile_chunk(*stmts, **kw) -> str:
  *stmts, last = stmts
  kw["defer"] = kw["defer"].copy()
  stmts = "\n".join(compile(s, **kw) for s in stmts)
  defers = "\n".join([compile(defer, **kw) for defer in kw["defer"]])
  kw["defer"] = []
  last = last and compile(last, **kw) or ""
  return stmts + "\n" + defers + last

def compile(tree, **kw) -> str:
  kw["this"] = tree
  kw["loc"] = get_loc(tree)
  if isinstance(tree, Token):
    return globals()["compile_" + tree.type](tree.value, **kw)
  return globals()["compile_" + tree.data](*tree.children, **kw)

def main() -> None:
  subprocess.run(["mkdir", ".complua"], capture_output=True)

  file = sys.argv[1]

  with open(file) as f:
    code = f.read()

  tree = parser.parse(code)
  env = {}
  type_env = types.copy()
  checkcall = {}
  using = []
  depens = []
  defer = []
  type = infer(tree, env=type_env, value_env=env, checkcall=checkcall, using=using, depens=depens, file=file, defer=defer)
  if isinstance(type, str):
    print(type)
    exit(1)
  result = compile(tree, env=env, type_env=type_env, checkcall=checkcall, using=using, value_env={}, depens=depens, file=file, defer=defer)
  with open("out.lua", "w") as f:
    f.write(format(result))

if __name__ == "__main__":
  main()
