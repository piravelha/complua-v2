from dataclasses import dataclass
from type_models import *
from typing import Any

@dataclass
class Node:
  data: str
  children: list['Node | str | Any']
  type: 'Type | None' = None
  @property
  def value(self):
    return self.children[0]