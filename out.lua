function check_person(name, age)
  assert(type(name) == "string");
  assert(type(age) == "number");
end
function Person(name, age)
  return {
    name = name,
    age = age,
  };
end
local p = Person("Ian", 15);