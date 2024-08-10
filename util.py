from lark import Tree, Token
from type_models import *

def get_loc(tree) -> int:
  if isinstance(tree, Token):
    return tree.line or 0
  if isinstance(tree, Tree):
    if tree.meta.empty:
      if tree.children:
        return get_loc(tree.children[0])
      return 0
    return tree.meta.line
  return 0

def unify(t1: AnyType, t2: AnyType, **kw) -> 'Type | str':

  if isinstance(t1, list):
    return unify(t1[0], t2, **kw)

  if isinstance(t2, list):
    return unify(t1, t2[0], **kw)

  if isinstance(t1, UnknownType):
    return t2
  
  if isinstance(t2, UnknownType):
    return t1
  
  if isinstance(t1, PrimitiveType) and isinstance(t2, PrimitiveType):
    if t1.name == t2.name:
      return t1
    return f"???:{t1.loc}: Primitive types don't unify: '{t1}' and '{t2}'"
  
  if isinstance(t1, TableType) and isinstance(t2, TableType):
    new = {}

    for k1, v1 in t1.fields.items():
      if not k1 in t2.fields:
        return f"???:{t1.loc}: Table type '{t2}' does not contain needed property '{k1}'"
      v2 = t2.fields[k1]
      x = unify(v1, v2, **kw)
      if isinstance(x, str): return x
      new[k1] = x

    for k2, v2 in t2.fields.items():
      if not k2 in t1.fields:
        return f"???:{t1.loc}: Table type '{t1}' does not contain needed property '{k2}'"
      v1 = t1.fields[k2]
      x = unify(v1, v2, **kw)
      if isinstance(x, str): return x
      new[k2] = x
      
    return TableType(new, t1.dependencies + t2.dependencies, t1.loc)
  
  if isinstance(t1, FunctionType) and isinstance(t2, FunctionType):

    ps1, _ = t1.tree.children
    ps2, _ = t2.tree.children
    if len(ps1.children) != len(ps2.children):
      return f"???:{t1.loc}: Function types '{t1}' and '{t2}' have different parameter counts"
    
    new = []
    for a, b in zip(t1.returns, t2.returns):
      x = unify(a, b, **kw)
      if isinstance(x, str): return x
      new.append(x)
    
    return FunctionType(new, t1.tree, None, t1.dependencies + t2.dependencies, False, t1.loc)
  
  return f"???:{t1.loc}: Types don't unify: '{t1}' and '{t2}'"

def filter_dependencies(type: Type) -> list[str]:
  deps = type.dependencies
  new: list[str] = []
  for dep in deps:
    if isinstance(dep, Token) and dep.type == "NAME" and dep.value not in new:
      new.append(dep.value)
  return new

def get_dependencies(tree: Tree, **kw) -> list[str]:
  from infer import infer
  from compiler import compile
  type = infer(tree, env=kw["type_env"], checkcall=kw["checkcall"])
  if isinstance(type, list): type = type[0] if type else NilType()
  if isinstance(type, str): raise TypeError(type)
  dep_list: list[list[str]] = []
  for dep in filter_dependencies(type):
    dep_tree = kw["env"][dep]
    dep_list.append(get_dependencies(dep_tree, **kw) + [compile(dep_tree, **kw)])
  flat_list = []
  for deps in dep_list:
    for dep in deps:
      if dep in flat_list:
        continue
      flat_list.append(dep)
  return flat_list

def replace_name(tree: Tree | Token, old: str, new: Tree | Token) -> Tree | Token:
  if isinstance(tree, Token):
    if tree.type == "NAME" and tree.value == old:
      return new
    return tree
  return Tree(tree.data, [replace_name(c, old, new) for c in tree.children])