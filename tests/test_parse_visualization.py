"""
End-to-end parse visualization test for Semantic XPath.
"""

import unittest

from pipeline_execution.semantic_xpath_parsing import QueryParser
from pipeline_execution.semantic_xpath_execution.execution_models import ParsedQueryAST


def _build_parsed_ast(parsed_query):
    steps = []
    for step in parsed_query.path.steps:
        steps.append({
            "axis": step.axis.value,
            "node_test_expr": step.test.to_dict(),
        })
    global_index = parsed_query.global_index.to_dict() if parsed_query.global_index else None
    return ParsedQueryAST(steps=steps, global_index=global_index)


class TestParseVisualization(unittest.TestCase):
    def test_full_parse_visualization(self):
        parser = QueryParser()
        queries = [
            # Global range + OR node tests + desc axis + agg_exists + NOT
            (
                "(/Itinerary/Day[1]/"
                "(POI[1][atom(content =~ \"museum\")] OR "
                "Restaurant[-1][atom(content =~ \"bistro\")])/"
                "desc::Attraction[agg_exists(desc::(POI OR Restaurant)[content =~ \"art\"]) "
                "AND not atom(content =~ \"closed\")])"
                "[-2:]"
            ),
            # Wildcard step + index range + AND/NOT in predicate
            (
                "/Itinerary/Day/.[1:2][atom(content =~ \"morning\")]/"
                "POI[atom(content =~ \"coffee\") AND not(atom(content =~ \"decaf\"))]"
            ),
            # Nested agg_exists -> agg_prev (1 level)
            (
                "/Itinerary/Day["
                "agg_exists(desc::POI["
                "agg_prev(desc::Review[atom(content =~ \"crowded\")]) "
                "AND atom(content =~ \"nearby\")"
                "])"
                "]"
            ),
            # Nested agg_prev -> agg_exists -> agg_prev (2 levels)
            (
                "/Itinerary["
                "agg_prev(desc::Day["
                "agg_exists(desc::POI["
                "agg_prev(desc::Review[atom(content =~ \"loud\")])"
                "]) AND atom(content =~ \"weekday\")"
                "])"
                "]"
            ),
            # Global single index + step range + OR predicate
            (
                "(/TodoList/Version[-1]/Project/Task[-3:]"
                "[atom(content =~ \"bug\") OR atom(content =~ \"critical\")])[1]"
            ),
        ]

        for idx, query in enumerate(queries):
            parsed = parser.parse(query)
            ast = _build_parsed_ast(parsed)
            visualization = ast.to_tree_string()
            print(f"\n=== Test Query {idx + 1} ===")
            print(query)
            print("\n=== Parsed Visualization ===")
            print(visualization)
            self.assertTrue(visualization)


if __name__ == "__main__":
    unittest.main(verbosity=2)
