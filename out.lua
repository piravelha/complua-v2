function Person(name, age)
  return {
    name = name,
    age = age,
    nested = {
      name2 = name,
      age2 = age
    }
  };
end

local ian = Person("Ian", 15);

print(ian.nested.name2, ian.nested.age2);

