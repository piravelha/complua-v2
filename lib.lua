_G["#COMPLUA"] = _G["#COMPLUA"] or {}

_G["#COMPLUA"].serialize = function(o)
  if type(o) == "string" then
    return '"' .. o .. '"'
  end
  if type(o) == "table" then
    local s = "{"
    local i = 1
    for k, v in pairs(o) do
      if i > 1 then
        s = s .. ", "
      end
      s = s .. "[" .. _G["#COMPLUA"].serialize(k) .. "] = " .. _G["#COMPLUA"].serialize(v)
      i = i + 1
    end
    return s .. "}"
  end
  if type(o) == "function" then
    local bytes = string.dump(o)
    local s = "load(string.char("
    for i = 1, #bytes do
      if i > 1 then
        s = s .. ", "
      end
      s = s .. tostring(string.byte(bytes, i))
    end
    return s .. "))"
  end
  return tostring(o)
end

local file = io.open(".complua/.eval.temp", "w")

