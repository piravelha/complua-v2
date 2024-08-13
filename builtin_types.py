from lark import Tree, Token
from type_models import *

types = {
  "assert": FunctionType(
    TupleType([]),
    Tree("func_body", [
      Tree("params", [
        Token("RAW_NAME", "assertion"),
        Tree("default_param", [
          Token("RAW_NAME", "message"),
          Token("STRING", "\"Assertion failed!\"")
        ]),
      ]),
      Tree("empty", []),
    ]),
  ),

  "type": FunctionType(
    TupleType([StringType([], 0)]),
    Tree("func_body", [
      Tree("params", [
        Token("RAW_NAME", "value"),
      ]),
      Tree("empty", [])
    ]),
  ),

  "print": FunctionType(
    TupleType([UnknownType([], False, 0)]),
    Tree("func_body", [
      Tree("params", [
        Token("RAW_NAME", "value")
      ]),
      Tree("empty", []),
    ]),
  ),
}
