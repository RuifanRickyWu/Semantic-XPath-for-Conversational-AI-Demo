"""Test parser for OR expression issue."""
from dense_xpath.parser import get_parser

p = get_parser()

# Test case: simple OR expression (should work)
test1 = "atom(content =~ \"kid\") OR atom(content =~ \"child\")"
print("Test 1:", test1)
parts = p._split_logical_operator(test1, ' OR ')
print("  Split parts:", parts)

# Test case: wrapped in parentheses (this is the issue)
test2 = "(atom(content =~ \"kid\") OR atom(content =~ \"child\"))"
print("\nTest 2:", test2)
parts = p._split_logical_operator(test2, ' OR ')
print("  Split parts:", parts)

# Parse the full expression
print("\n--- Parsing full predicate string ---")
pred_str = "(atom(content =~ \"kid\") OR atom(content =~ \"child\"))"
result = p._parse_logical_predicate(pred_str)
print("Result operator:", result.operator)
print("Result conditions:", result.conditions)
