"""
Query endpoint for executing CRUD operations.

POST /api/query - Execute a natural language query
"""

from flask import Blueprint, request, jsonify, current_app
from pipeline.serializers import serialize_result, serialize_tree

bp = Blueprint("query", __name__)


@bp.route("/query", methods=["POST"])
def execute_query():
    """
    Execute a natural language CRUD query.
    
    Request body:
        {
            "query": "find museums in the itinerary"
        }
        
    Returns:
        Full pipeline result with tree state before/after
    """
    data = request.get_json()
    
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400
    
    query = data["query"].strip()
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400
    
    pipeline = current_app.pipeline
    
    try:
        # Capture tree state before operation
        tree_before = serialize_tree(pipeline.executor.tree.getroot())
        
        # Execute the query
        result = pipeline.process_request(query)
        
        # Capture tree state after operation
        tree_after = serialize_tree(pipeline.executor.tree.getroot())
        
        # Build response
        response = serialize_result(result)
        response["tree"] = {
            "before": tree_before,
            "after": tree_after
        }
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "success": False
        }), 500
