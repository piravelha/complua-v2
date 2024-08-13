function Person(name, age, hobbies)
  return {
    name = name,
    age = age,
    greet = function(other)
    print(string.format("Hello %s!, i am %s, nice to meet you.", other.name, name));
  end,
};
end
local immutable_hobbies = {
"programming",
};
local mutable_hobbies = {
"gaming",
};
local p1 = Person("Ian", 15, immutable_hobbies);
local p2 = Person("Miguel", 5, mutable_hobbies);
p1.greet(p2);