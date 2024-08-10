from dataclasses import dataclass
from typing import TypeAlias
from lark import Tree

Type: TypeAlias = 'PrimitiveType | UnknownType | TableType | FunctionType'
AnyType: TypeAlias = 'Type | TupleType'

@dataclass
class PrimitiveType:
  name: str
  dependencies: list[Tree]
  loc: int
  def __repr__(self):
    return self.name

def NumberType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("number", dependencies, loc)
def StringType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("string", dependencies, loc)
def BooleanType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("boolean", dependencies, loc)
def NilType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("nil", dependencies, loc)

@dataclass
class UnknownType:
  dependencies: list[Tree]
  loc: int
  def __repr__(self):
    return "unknown"
  
@dataclass
class TableType:
  fields: dict[str, Type]
  dependencies: list[Tree]
  loc: int
  def __repr__(self):
    fields = [f"{k}: {v}" for k, v in self.fields.items()]
    return "{" + ", ".join(fields) + "}"
  
@dataclass
class FunctionType:
  returns: 'TupleType'
  tree: Tree
  checkcall: Tree | None
  dependencies: list[Tree]
  inline: bool
  loc: int
  def __init__(
      self,
      returns: AnyType,
      tree: Tree,
      checkcall: Tree | None,
      dependencies: list[Tree],
      inline: bool,
      loc: int):
    if not isinstance(returns, TupleType):
      returns = TupleType([returns])
    self.returns = returns
    self.tree = tree
    self.checkcall = checkcall
    self.dependencies = dependencies
    self.inline = inline
    self.loc = loc
  def __repr__(self):
    params, _ = self.tree.children
    params = ", ".join([f"{p}" for p in params.children])
    returns = ", ".join(f"{r}" for r in self.returns.values)
    return f"({params}) -> {returns}"
  
@dataclass
class TupleType:
  values: list[Type]
  def __init__(self, values: list[Type], dependencies: list[Tree] = []):
    self.values = values
    self.dependencies = dependencies
  def __repr__(self):
    return "(" + ", ".join(f"{v}" for v in self.values) + ")"