import re

def format(code: str, indent: int = 2) -> str:
  indentation = 0
  lines = []
  for line in code.splitlines():
    if not line.strip(): continue
    if re.match(r"\bend\b", line):
      indentation -= 1
    if "}" in line:
      indentation -= line.count("}") - line.count("{")
    lines.append(" " * indent * indentation + line.lstrip())
    if re.match(r"\bfunction\b", line):
      indentation += 1
    if "{" in line:
      indentation += line.count("{") - line.count("}")
  return "\n".join(lines)
