function Person(name, age)
  return {
    nested = {
      name2 = name,
      age2 = age,
    },
  };
end
local ian = Person("Ian", 15);
local name2 = 10;
print(name2, ian.nested.age2);
