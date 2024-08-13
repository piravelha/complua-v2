import os
from lark import Lark

script_path = os.path.abspath(__file__)
path = os.path.dirname(script_path)

parser = Lark.open(path + "/grammar.lark")
any_parser = Lark.open(path + "/grammar.lark", start="any_rule")
