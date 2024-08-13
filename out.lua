local function mutate(x)
x[1] = 1;
print("YIPPE");
end
local tbl = {
};
mutate(tbl);
unpack({})