// BAML Schema for Knowledge Graph Extraction
// This defines the structure for nodes and edges in our knowledge graph

class Node {
  id string @description("Unique identifier for the node")
  label string @description("The type of entity, e.g., 'Product', 'Organization', 'Person', 'Technology'")
  properties map<string, string> @description("Additional properties as key-value pairs")
}

class Edge {
  source_id string @description("The ID of the source node")
  target_id string @description("The ID of the target node")
  relationship_type string @description("The predicate/relationship type, e.g., 'ENABLES', 'DEPENDS_ON', 'ACQUIRES', 'USES'")
}

class KnowledgeGraph {
  nodes Node[] @description("List of all nodes in the knowledge graph")
  edges Edge[] @description("List of all edges/relationships in the knowledge graph")
}

class QueryPath {
  nodes string[] @description("List of node IDs in the traversal path")
  relationships string[] @description("List of relationship types traversed")
}

// Function to extract knowledge graph from unstructured text
function ExtractGraph(text: string) -> KnowledgeGraph {
  client Gemini
  prompt #"
    Analyze the following text and extract a knowledge graph based on the defined schema.
    
    Extract entities (nodes) and their relationships (edges) from the text. For each entity:
    - Assign a unique ID (use a short, descriptive identifier)
    - Assign an appropriate label (Product, Organization, Person, Technology, Concept, etc.)
    - Extract relevant properties (name, description, type, etc.)
    
    For relationships:
    - Identify how entities relate to each other
    - Use clear relationship types like: ENABLES, DEPENDS_ON, ACQUIRES, USES, CREATES, IMPLEMENTS, etc.
    - Ensure source_id and target_id reference valid node IDs
    
    TEXT TO ANALYZE:
    {{ text }}
    
    {{ ctx.output_format }}
    
    Ensure strict adherence to the schema. Return a valid KnowledgeGraph with nodes and edges arrays.
    All node IDs referenced in edges must exist in the nodes array.
  "#
}

class ChatResponse {
  answer string @description("The answer to the user's question")
  confidence string @description("HIGH if answer is based on graph context, LOW if inferred or not found, MEDIUM if partially found")
  relevant_node_ids string[] @description("List of node IDs that are relevant to the answer")
  suggested_queries string[] @description("Suggested follow-up queries to explore the graph")
}

// Function for chat interface with improved graph querying
function ChatWithGraph(question: string, graph_context: string) -> ChatResponse {
  client Gemini
  prompt #"
    You are a helpful assistant that answers questions about a knowledge graph.
    
    Knowledge Graph Context:
    {{ graph_context }}
    
    User Question: {{ question }}
    
    Instructions:
    1. Analyze the question and identify which nodes and relationships from the graph are relevant
    2. If the answer can be directly found in the graph context, set confidence to "HIGH" and provide the answer
    3. If the answer requires inference or connecting multiple nodes, set confidence to "MEDIUM" and explain your reasoning
    4. If the answer cannot be found in the graph context, set confidence to "LOW" and provide a generic answer with a note that it may be unreliable
    5. List all relevant node IDs that relate to the answer
    6. Suggest 2-3 follow-up queries that would help explore related information in the graph
    
    Be concise and accurate. Always indicate when information is not directly available in the graph.
    
    {{ ctx.output_format }}
  "#
}
