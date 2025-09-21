#!/usr/bin/env python3
"""
Generate LangGraph visualization
"""
import os
from src.services.conversation import FrenchNewsConversationAgent
from langchain_core.runnables.graph import MermaidDrawMethod 

def main():
    # We can use a dummy API key just for graph generation
    dummy_api_key = "dummy-key-for-graph-generation"
    
    print("🚀 Creating conversation agent (for graph structure only)...")
    agent = FrenchNewsConversationAgent(dummy_api_key)
    
    print("📊 Generating graph visualization...")
    
    try:
        # Generate PNG image using local Pyppeteer method
        print("🔄 Using local browser rendering (Pyppeteer)...")
        png_data = agent.graph.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.PYPPETEER,)
        
        # Save PNG to file
        with open("langgraph_diagram.png", "wb") as f:
            f.write(png_data)
        
        print("✅ PNG diagram generated!")
        print("💾 Saved to langgraph_diagram.png")
        
        # Also generate mermaid code for reference
        mermaid_code = agent.graph.get_graph().draw_mermaid()
        with open("langgraph_diagram.md", "w") as f:
            f.write("```mermaid\n")
            f.write(mermaid_code)
            f.write("\n```")
        
        print("📝 Mermaid code also saved to langgraph_diagram.md")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
