import subprocess
from lark import Token, Tree
from parser import parser
from type_models import *
from util import get_loc, get_dependencies, replace_name
from infer import infer

def get_using(path, current=None, **kw):
  if current is None:
    current = kw["type_env"]
  first, *rest = path
  type = current[first.value]
  assert isinstance(type, TableType)
  if not rest: return type
  return get_using(rest, type.fields, **kw)

def compile_NAME(value, **kw) -> str:
  for using_path in kw["using"]:
    using = get_using(using_path, **kw)
    assert isinstance(using, TableType)
    path_str = ".".join(using_path)
    if value in using.fields:
      return f"{path_str}.{value}"
  return value

def compile_RAW_NAME(value, **kw) -> str:
  return value
 
def compile_NUMBER(value, **kw) -> str:
  return value

def compile_STRING(value, **kw) -> str:
  return value

def compile_BOOLEAN(value, **kw) -> str:
  return value

def compile_NIL(value, **kw) -> str:
  return value

def compile_paren(expr, **kw) -> str:
  return "(" + compile(expr, **kw) + ")"

def compile_table(*fields, **kw) -> str:
  code = "{"
  for i, field in enumerate(fields):
    key, value = field.children
    if i > 0: code += ", "
    value = compile(value, **kw)
    code += f"{key} = {value}"
  return code + "}"

def compile_prop_expr(prefix, prop, **kw) -> str:
  prefix = compile(prefix, **kw)
  return f"{prefix}.{prop.value}"

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
compile_eq_expr = compile_math_expr
compile_and_expr = compile_math_expr
compile_or_expr = compile_math_expr

def compile_func_body(params, body, **kw) -> str:
  body = compile(body, **kw)
  params = ", ".join(compile(p, **kw) for p in params.children)
  return f"({params})\n{body}\nend"

def compile_func_expr(func, **kw) -> str:
  return "function" + compile(func, **kw)

def compile_func_call(prefix, args, **kw) -> str:
  prefix_type = infer(prefix, env=kw["type_env"], checkcall=kw["checkcall"], value_env=kw["env"])
  if isinstance(prefix_type, FunctionType):
    if prefix_type.inline:
      params, body = prefix_type.tree.children
      for p, a in zip(params.children, args.children):
        assert isinstance(p, Token)
        body = replace_name(body, p.value, a)
      return f"(function()\n" + compile(body, **kw) + "\nend)()"
    if prefix_type.checkcall:
      body = prefix_type.checkcall
      compile_eval(
        Tree("func_call", [
          Tree("paren", [
            Tree("func_expr", [body])
          ]),
          args,
        ]), **kw)
  prefix = compile(prefix, **kw)
  args = ", ".join(compile(a, **kw) for a in args.children)
  return f"{prefix}({args})"

def compile_call_stmt(call, **kw) -> str:
  return compile(call, **kw) + ";"

def compile_func_decl(name, func, **kw) -> str:
  kw["env"][name.value] = kw["this"]
  func = compile(func, **kw)
  return f"function {name}{func}"

def compile_local_func_decl(name, func, **kw) -> str:
  kw["env"][name.value] = kw["this"]
  func = compile(func, **kw)
  return f"local function {name}{func}"

def compile_var_decl(names, exprs, **kw) -> str:
  for name, expr in zip(names.children, exprs.children):
    kw["env"][name.value] = Tree("var_decl", [Tree("names", [name]), Tree("exprs", [expr])])
  names = ", ".join(compile(n, **kw) for n in names.children)
  exprs = ", ".join(compile(e, **kw) for e in exprs.children)
  return f"local {names} = {exprs};"

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

def compile_return_stmt(exprs, **kw) -> str:
  if not exprs:
    exprs = ""
  else:
    exprs = ", ".join(compile(e, **kw) for e in exprs.children)
  return f"return {exprs};"

def compile_eval(expr, **kw) -> str:
  #try:
  old_expr = expr
  #except KeyError as e: # attempting to evaluate
  #  print(
  #    f"???:{kw['loc']}: Could not evaluate '#eval' directive, " \
  #    + f"variable '{e.args[0]}' is not statically known.")
  #  exit(1)
  path = "./.complua/.eval"
  expr = compile(expr, **kw)
  code = f"\n\nlocal __eval = {{ {expr} }};\n"
  code += f"file:write(_G['#COMPLUA'].serialize(__eval));\n"
  code += f"file:close();\n"
  with open("lib.lua") as f:
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

def compile_inline(func_decl, **kw) -> str:
  return compile(func_decl, **kw)

def compile_checkcall(name, body, **kw) -> str:
  return ""

def compile_using(*names, **kw):
  kw["using"].append(names)
  return ""

def compile_chunk(*stmts, **kw) -> str:
  *stmts, last = stmts
  stmts = "\n".join(compile(s, **kw) for s in stmts)
  last = last and compile(last, **kw) or ""
  return stmts + "\n" + last

def compile(tree, **kw) -> str:
  kw["this"] = tree
  kw["loc"] = get_loc(tree)
  if isinstance(tree, Token):
    return globals()["compile_" + tree.type](tree.value, **kw)
  return globals()["compile_" + tree.data](*tree.children, **kw)

def main() -> None:
  subprocess.run(["mkdir", ".complua"], capture_output=True)

  with open("demo.clua") as f:
    code = f.read()

  tree = parser.parse(code)
  env = {}
  type_env = {}
  checkcall = {}
  using = []
  type = infer(tree, value_env=env, env=type_env, checkcall=checkcall, using=using)
  if isinstance(type, str):
    raise TypeError(type)
  result = compile(tree, env=env, type_env=type_env, checkcall=checkcall, using=using)
  with open("out.lua", "w") as f:
    f.write(result)

if __name__ == "__main__":
  main()
