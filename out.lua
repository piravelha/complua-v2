function add(x)
  function inner(y)
    return x + y;
  end
  return inner;
end
unpack({})