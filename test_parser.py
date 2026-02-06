"""Quick sanity check for predicate parsing."""
from pipeline_execution.semantic_xpath_parsing import get_parser, parse_predicate

p = get_parser()

test1 = "atom(content =~ \"kid\") OR atom(content =~ \"child\")"
print("Test 1:", test1)
print("Parsed:", parse_predicate(test1))

test2 = "(atom(content =~ \"kid\") OR atom(content =~ \"child\"))"
print("\nTest 2:", test2)
print("Parsed:", parse_predicate(test2))

query = "/Itinerary/Day/POI[atom(content =~ \"museum\")]"
parsed = p.parse(query)
print("\n--- Parsed query ---")
print(parsed)
