"""Simple web app for knowledge graph extraction and visualization."""

import os
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.extractor import extract_text_from_html, extract_text_from_file, preprocess_text
from src.database_loader import Neo4jLoader

# Import BAML client
try:
    from baml_client import b
    from baml_client.types import KnowledgeGraph, ChatResponse
except ImportError:
    print("⚠️  BAML client not found. Please run: baml-cli generate")
    b = None
    KnowledgeGraph = None
    ChatResponse = None

# Store current graph context for chat
current_graph_context = None

app = FastAPI(title="Knowledge Graph Extractor")

# Neo4j configuration
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web interface."""
    try:
        with open("templates/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="Template file not found. Please ensure templates/index.html exists.", status_code=500)


@app.post("/extract")
async def extract(files: Optional[List[UploadFile]] = File(None), text: Optional[str] = Form(None)):
    """Extract knowledge graph from text or file(s)."""
    if not b:
        raise HTTPException(status_code=500, detail="BAML client not configured")
    
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set in .env file")
    
    # Get text content
    content = ""
    if files and len(files) > 0:
        # Handle multiple files
        all_texts = []
        for file in files:
            if not file.filename:
                continue
            file_bytes = await file.read()
            try:
                file_text = extract_text_from_file(file_bytes, file.filename)
                if file_text.strip():
                    all_texts.append(f"--- Content from {file.filename} ---\n{file_text}")
            except Exception as e:
                print(f"Warning: Failed to extract text from {file.filename}: {str(e)}")
                continue
        if all_texts:
            content = "\n\n".join(all_texts)
        else:
            raise HTTPException(status_code=400, detail="Failed to extract text from any uploaded files")
    elif text:
        # Check if it's a URL
        if text.startswith('http://') or text.startswith('https://'):
            from src.extractor import fetch_url
            html = fetch_url(text)
            if html:
                content = extract_text_from_html(html)
            else:
                raise HTTPException(status_code=400, detail="Failed to fetch URL")
        else:
            content = text
    else:
        raise HTTPException(status_code=400, detail="Either text or file(s) must be provided")
    
    content = preprocess_text(content)
    
    # Extract graph using BAML
    try:
        # BAML client is async, so we need to await it
        graph_data: KnowledgeGraph = await b.ExtractGraph(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    # Store graph context for chat
    global current_graph_context
    graph_response = {
        "nodes": [
            {
                "id": node.id,
                "label": node.label,
                "properties": node.properties or {}
            }
            for node in graph_data.nodes
        ],
        "edges": [
            {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relationship_type": edge.relationship_type
            }
            for edge in graph_data.edges
        ]
    }
    current_graph_context = graph_response
    
    # Load into Neo4j
    try:
        loader = Neo4jLoader(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
        if loader.verify_connection():
            loader.upload_graph(graph_data)
        loader.close()
    except Exception as e:
        print(f"⚠️  Failed to load to Neo4j: {e}")
    
    # Return response
    return graph_response


@app.get("/graph")
async def get_graph():
    """Get the current graph from Neo4j."""
    try:
        loader = Neo4jLoader(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
        if not loader.verify_connection():
            raise HTTPException(status_code=503, detail="Cannot connect to Neo4j")
        
        driver = loader.driver
        with driver.session() as session:
            # Get all nodes
            node_result = session.run("MATCH (n:Entity) RETURN n.id as id, n.label as label, n as props")
            nodes = []
            for record in node_result:
                props = dict(record["props"])
                props.pop("id", None)
                props.pop("label", None)
                nodes.append({
                    "id": record["id"],
                    "label": record["label"],
                    "properties": props
                })
            
            # Get all relationships
            edge_result = session.run("""
                MATCH (a:Entity)-[r]->(b:Entity)
                RETURN a.id as source_id, b.id as target_id, type(r) as relationship_type
            """)
            edges = [
                {
                    "source_id": record["source_id"],
                    "target_id": record["target_id"],
                    "relationship_type": record["relationship_type"]
                }
                for record in edge_result
            ]
        
        loader.close()
        
        graph_data = {"nodes": nodes, "edges": edges}
        
        # Store graph context for chat
        global current_graph_context
        current_graph_context = graph_data
        
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load graph: {str(e)}")


class ChatRequest(BaseModel):
    question: str
    graph_context: Optional[str] = None


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat with the knowledge graph using LLM."""
    if not b:
        raise HTTPException(status_code=500, detail="BAML client not configured")
    
    global current_graph_context
    if not current_graph_context:
        raise HTTPException(status_code=400, detail="No graph loaded. Please extract a graph first.")
    
    # Create enhanced graph context string with more information
    graph_context_str = f"Graph has {len(current_graph_context['nodes'])} nodes and {len(current_graph_context['edges'])} edges.\n\n"
    graph_context_str += "Nodes:\n"
    for node in current_graph_context['nodes'][:50]:  # Increased limit for better context
        graph_context_str += f"- {node['label']} (ID: {node['id']})\n"
        if node.get('properties'):
            for k, v in node['properties'].items():
                graph_context_str += f"  {k}: {v}\n"
    
    graph_context_str += "\nRelationships:\n"
    for edge in current_graph_context['edges'][:50]:  # Increased limit
        graph_context_str += f"- {edge['source_id']} --[{edge.get('relationship_type', 'RELATED_TO')}]--> {edge['target_id']}\n"
    
    try:
        chat_response: ChatResponse = await b.ChatWithGraph(request.question, graph_context_str)
        
        # Extract path using relevant node IDs from the response
        path = extract_path_from_nodes(chat_response.relevant_node_ids, current_graph_context)
        
        # Add caution message if confidence is LOW
        answer_text = chat_response.answer
        if chat_response.confidence == "LOW":
            answer_text = f"⚠️ **Note:** This answer may be unreliable as the information was not found in the knowledge graph.\n\n{answer_text}"
        
        return {
            "answer": answer_text,
            "confidence": chat_response.confidence,
            "path": path,
            "suggested_queries": chat_response.suggested_queries or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


def extract_path_from_nodes(node_ids: List[str], graph_context: dict) -> Optional[dict]:
    """Extract paths between relevant nodes using multi-hop traversal."""
    if not graph_context or not graph_context.get('nodes') or not node_ids:
        return None
    
    # Filter to only valid node IDs that exist in the graph
    valid_node_ids = [nid for nid in node_ids if any(n['id'] == nid for n in graph_context['nodes'])]
    
    if not valid_node_ids:
        return None
    
    # If only one node, return it
    if len(valid_node_ids) == 1:
        return {"nodes": valid_node_ids}
    
    try:
        loader = Neo4jLoader(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
        if not loader.verify_connection():
            loader.close()
            return {"nodes": valid_node_ids[:5]}  # Fallback
        
        driver = loader.driver
        with driver.session() as session:
            # Strategy 1: Find all paths between relevant nodes (multi-hop)
            # Use variable length paths up to 3 hops
            paths_found = []
            
            # Try to find paths between pairs of relevant nodes
            for i in range(len(valid_node_ids)):
                for j in range(i + 1, len(valid_node_ids)):
                    result = session.run("""
                        MATCH path = shortestPath(
                            (a:Entity {id: $start_id})-[*..3]-(b:Entity {id: $end_id})
                        )
                        RETURN [node in nodes(path) | node.id] as node_ids,
                               [rel in relationships(path) | type(rel)] as rel_types
                        LIMIT 1
                    """, start_id=valid_node_ids[i], end_id=valid_node_ids[j])
                    
                    record = result.single()
                    if record and record["node_ids"]:
                        paths_found.append({
                            "nodes": record["node_ids"],
                            "relationships": record["rel_types"]
                        })
            
            # If we found paths, return the longest/most comprehensive one
            if paths_found:
                # Sort by path length (more nodes = better)
                paths_found.sort(key=lambda x: len(x["nodes"]), reverse=True)
                loader.close()
                return paths_found[0]
            
            # Strategy 2: Find nodes connected to the relevant nodes (1-hop expansion)
            if len(valid_node_ids) >= 2:
                result = session.run("""
                    MATCH (start:Entity {id: $start_id})-[r*..2]-(connected:Entity)
                    WHERE connected.id IN $node_ids
                    WITH collect(DISTINCT connected.id) + [$start_id] as all_nodes
                    RETURN all_nodes[0..10] as node_ids
                """, start_id=valid_node_ids[0], node_ids=valid_node_ids[1:])
                
                record = result.single()
                if record and record["node_ids"]:
                    loader.close()
                    return {"nodes": record["node_ids"]}
            
            loader.close()
            
    except Exception as e:
        print(f"Warning: Path extraction failed: {e}")
    
    # Fallback: return relevant nodes
    return {"nodes": valid_node_ids[:5]}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Knowledge Graph Extractor...")
    print("📊 Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)

