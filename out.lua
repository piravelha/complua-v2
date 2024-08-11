function expect_type(value, str)
if type(value) ~= str then
error("Expected '" .. str .. "', but got " .. "'" .. type(value) .. "' instead");

end

end

function Person(name, age)

function greet(other)
print("Hello, other");

end
return {is_person = true, name = name, age = age, greet = greet};
end
local p1 = Person("Ian", 15);
local p2 = Person("Miguel", 5);
p1.greet(p2);
