from type_models import *

def unify(t1: AnyType, t2: AnyType, **kw) -> 'Type | str':

  if isinstance(t1, list):
    return unify(t1[0], t2)

  if isinstance(t2, list):
    return unify(t1, t2[0])

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
      
    return TableType(new, t1.loc)
  
  if isinstance(t1, FunctionType) and isinstance(t2, FunctionType):

    ps1, _ = t1.tree.children
    ps2, _ = t2.tree.children
    if len(ps1.children) != len(ps2.children):
      return f"???:{t1.loc}: Function types '{t1}' and '{t2}' have different parameter counts"
    
    new = []
    for a, b in zip(t1.returns, t2.returns):
      x = unify(a, b)
      if isinstance(x, str): return x
      new.append(x)
    
    return FunctionType(new, t1.tree, t1.loc)
  
  return f"???:{t1.loc}: Types don't unify: '{t1}' and '{t2}'"
