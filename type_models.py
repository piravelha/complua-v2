from dataclasses import dataclass
from re import S
from typing import Any, TypeAlias
from lark import Tree

Type: TypeAlias = 'PrimitiveType | UnknownType | TableType | DictType | FunctionType'
AnyType: TypeAlias = 'Type | TupleType'

@dataclass
class PrimitiveType:
  name: str
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  mutable: bool = False
  literal: bool = False
  def __repr__(self):
    return self.name
  def copy(self):
    return PrimitiveType(self.name, self.dependencies, self.is_parameter, self.loc, self.mutable, self.literal)

def NumberType(dependencies: list[Tree] = [], loc = 0, mutable = True, literal = False):
  return PrimitiveType("number", dependencies, False, loc, mutable, literal)

def StringType(dependencies: list[Tree] = [], loc = 0, mutable = True, literal = False):
  return PrimitiveType("string", dependencies, False, loc, mutable, literal)

def BooleanType(dependencies: list[Tree] = [], loc = 0, mutable = True, literal = False):
  return PrimitiveType("boolean", dependencies, False, loc, mutable, literal)

def NilType(dependencies: list[Tree] = [], loc = 0, mutable = True, literal = False):
  return PrimitiveType("nil", dependencies, False, loc, mutable, literal)

@dataclass
class UnknownType:
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  mutable: bool = False
  def __repr__(self):
    return "unknown"
  def copy(self):
    return UnknownType(self.dependencies, self.is_parameter, self.loc, self.mutable)

@dataclass
class TableType:
  fields: dict[str, Type]
  name: str | None
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  mutable: bool = False
  def __repr__(self):
    if self.name: return self.name
    fields = [f"{k}: {v}" for k, v in self.fields.items()]
    return "{" + ", ".join(fields) + "}"
  def copy(self):
    return TableType(self.fields, self.name, self.dependencies, self.is_parameter, self.loc, self.mutable)
  
@dataclass
class DictType:
  key: Type
  value: Type
  dependencies: list[Tree]
  is_parameter: bool
  loc: int
  mutable: bool = False
  def __repr__(self):
    return f"{{ [{self.key}]: {self.value} }}"
  def copy(self):
    return DictType(self.key, self.value, self.dependencies, self.is_parameter, self.loc, self.mutable)

@dataclass
class FunctionType:
  returns: 'TupleType'
  tree: Tree
  checkcalls: list[Tree]
  dependencies: list[Tree]
  inline: bool
  is_parameter: bool
  loc: Any
  def __init__(
      self,
      returns: AnyType,
      tree: Tree,
      checkcalls: list[Tree] = [],
      dependencies: list[Tree] = [],
      inline: bool = False,
      is_parameter: bool = False,
      mutable: bool = False,
      loc = "0:0"):
    if not isinstance(returns, TupleType):
      returns = TupleType([returns])
    self.returns = returns
    self.tree = tree
    self.checkcalls = checkcalls
    self.dependencies = dependencies
    self.inline = inline
    self.is_parameter = is_parameter
    self.loc = loc
    self.mutable = mutable
  def __repr__(self):
    params, _ = self.tree.children
    params = ", ".join([f"{p}" for p in params.children])
    returns = ", ".join(f"{r}" for r in self.returns.values)
    return f"({params}) -> {returns}"
  def copy(self):
    return FunctionType(self.returns, self.tree, self.checkcalls, self.dependencies, self.inline, self.is_parameter, self.loc, self.mutable)
  
@dataclass
class TupleType:
  values: list[Type]
  is_parameter: bool
  mutates: Any
  def __init__(self, values: list[Type], dependencies: list[Tree] = [], mutates: list[str] = []):
    self.values = values
    self.dependencies = dependencies
    self.mutates = mutates
  def __repr__(self):
    return "(" + ", ".join(f"{v}" for v in self.values) + ")"
  def copy(self):
    return TupleType(self.values, self.dependencies, self.mutates)
