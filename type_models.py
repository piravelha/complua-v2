from dataclasses import dataclass
from typing import TypeAlias
from lark import Tree
from lark.utils import Serialize

Type: TypeAlias = 'PrimitiveType | UnknownType | TableType | FunctionType'
AnyType: TypeAlias = 'Type | TupleType'

@dataclass
class PrimitiveType:
  name: str
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  def __repr__(self):
    return self.name
  def copy(self):
    return PrimitiveType(self.name, self.dependencies, self.is_parameter, self.loc)

def NumberType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("number", dependencies, False, loc)
def StringType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("string", dependencies, False, loc)
def BooleanType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("boolean", dependencies, False, loc)
def NilType(dependencies: list[Tree] = [], loc = 0):
  return PrimitiveType("nil", dependencies, False, loc)

@dataclass
class UnknownType:
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  def __repr__(self):
    return "unknown"
  def copy(self):
    return UnknownType(self.dependencies, self.is_parameter, self.loc)

@dataclass
class TableType:
  fields: dict[str, Type]
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  def __repr__(self):
    fields = [f"{k}: {v}" for k, v in self.fields.items()]
    return "{" + ", ".join(fields) + "}"
  def copy(self):
    return TableType(self.fields, self.dependencies, self.is_parameter, self.loc)
  
@dataclass
class FunctionType:
  returns: 'TupleType'
  tree: Tree
  checkcall: Tree | None
  dependencies: list[Tree]
  inline: bool
  is_parameter: bool
  loc: int
  def __init__(
      self,
      returns: AnyType,
      tree: Tree,
      checkcall: Tree | None,
      dependencies: list[Tree],
      inline: bool,
      is_parameter: bool,
      loc: int):
    if not isinstance(returns, TupleType):
      returns = TupleType([returns])
    self.returns = returns
    self.tree = tree
    self.checkcall = checkcall
    self.dependencies = dependencies
    self.inline = inline
    self.is_parameter = is_parameter
    self.loc = loc
  def __repr__(self):
    params, _ = self.tree.children
    params = ", ".join([f"{p}" for p in params.children])
    returns = ", ".join(f"{r}" for r in self.returns.values)
    return f"({params}) -> {returns}"
  def copy(self):
    return FunctionType(self.returns, self.tree, self.checkcall, self.dependencies, self.inline, self.is_parameter, self.loc)
  
@dataclass
class TupleType:
  values: list[Type]
  is_parameter: bool = False
  def __init__(self, values: list[Type], dependencies: list[Tree] = []):
    self.values = values
    self.dependencies = dependencies
  def __repr__(self):
    return "(" + ", ".join(f"{v}" for v in self.values) + ")"
  def copy(self):
    return TupleType(self.values, self.dependencies)
