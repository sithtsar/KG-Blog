"""Neo4j database loader for knowledge graph data."""

import re
from neo4j import GraphDatabase
from typing import List, Dict, Any


class Neo4jLoader:
    """Handles loading knowledge graph data into Neo4j."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        """Initialize Neo4j driver."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the database connection."""
        self.driver.close()
    
    def upload_graph(self, graph_data: Any) -> None:
        """
        Upload knowledge graph data to Neo4j.
        
        Args:
            graph_data: KnowledgeGraph object from BAML with nodes and edges
        """
        with self.driver.session() as session:
            # 1. Merge Nodes (idempotent - won't create duplicates)
            for node in graph_data.nodes:
                # Create node with label from the node.label field
                # Use MERGE to ensure idempotency
                session.run("""
                    MERGE (n:Entity {id: $id})
                    SET n.label = $label
                    SET n += $props
                """, 
                id=node.id, 
                label=node.label, 
                props=node.properties or {})
            
            # 2. Merge Relationships
            # Note: Neo4j requires relationship types to be known at query time
            # We'll sanitize and use string formatting for the relationship type
            for edge in graph_data.edges:
                # Sanitize relationship type: keep only alphanumeric and underscores
                rel_type = re.sub(r'[^A-Za-z0-9_]', '_', edge.relationship_type.upper())
                # Remove consecutive underscores
                rel_type = re.sub(r'_+', '_', rel_type).strip('_')
                if not rel_type:
                    rel_type = "RELATED_TO"  # Default if sanitization removes everything
                
                # Use f-string for dynamic relationship type (safe after sanitization)
                query = f"""
                    MATCH (source:Entity {{id: $source_id}})
                    MATCH (target:Entity {{id: $target_id}})
                    MERGE (source)-[:{rel_type}]->(target)
                """
                session.run(query, 
                    source_id=edge.source_id,
                    target_id=edge.target_id)
            
            print(f"✓ Loaded {len(graph_data.nodes)} nodes and {len(graph_data.edges)} edges into Neo4j")
    
    def verify_connection(self) -> bool:
        """Verify connection to Neo4j."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as x")
                return result.single() is not None
        except Exception as e:
            print(f"✗ Failed to connect to Neo4j: {e}")
            return False

