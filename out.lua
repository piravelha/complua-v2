local framerate = 60;
local function map(tbl, fn)
local new = {
};
for idx, it in pairs(tbl) do
new[idx] = fn(it);
end
return new;
end
local function main()
local array = {
1,
2,
3,
};
local new = map(array, function(x)
return x * framerate;
end);
for idx, it in pairs(new) do
print(it);
end
end
unpack({})