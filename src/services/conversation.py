from typing import Dict, List, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import logging
import asyncio

from src.services.news_processor import news_processor
from src.database.client import db_client

logger = logging.getLogger(__name__)


class QueryAnalysis(BaseModel):
    """Structured model for query analysis results"""
    keywords: str = Field(description="Relevant keywords extracted from the query, comma-separated")
    language: str = Field(description="Preferred response language", pattern="^(french|english)$")
    intent: str = Field(description="User intent classification", pattern="^(news_discussion|general_chat)$")


class ConversationState:
    def __init__(self):
        self.messages: List[Dict] = []
        self.relevant_articles: List[Dict] = []
        self.conversation_id: Optional[str] = None
        self.language: str = "french"  # Default to French for B1 learners


class FrenchNewsConversationAgent:
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4",
            temperature=0.7
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph conversation flow"""
        
        def analyze_query_node(state: Dict) -> Dict:
            """Analyze user query and determine intent"""
            user_message = state["messages"][-1]["content"]
            
            # Use structured output with Pydantic model
            structured_llm = self.llm.with_structured_output(QueryAnalysis)
            
            analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are analyzing a user query about French news. Determine:
                1. Is this about specific news topics or general conversation?
                2. What keywords should we use to find relevant articles?
                3. Should we respond in French or English?
                
                For keywords: extract the most relevant terms that would help find news articles.
                For language: choose "french" for French learners (default) or "english" if specifically requested.
                For intent: choose "news_discussion" for news-related queries or "general_chat" for other conversations."""),
                ("human", "{query}")
            ])
            
            try:
                analysis: QueryAnalysis = structured_llm.invoke(
                    analysis_prompt.format_messages(query=user_message)
                )
                state["query_analysis"] = analysis.model_dump()
                state["language"] = analysis.language
            except Exception as e:
                logger.warning(f"Structured output failed, using fallback: {e}")
                # Fallback to default values
                state["query_analysis"] = {
                    "keywords": user_message,
                    "language": "french",
                    "intent": "news_discussion"
                }
                state["language"] = "french"
            
            return state

        def retrieve_articles_node(state: Dict) -> Dict:
            """Retrieve relevant news articles"""
            analysis = state.get("query_analysis", {})
            keywords = analysis.get("keywords", state["messages"][-1]["content"])
            
            try:
                # Use the simple synchronous method
                relevant_articles = news_processor.get_articles_for_conversation_sync(
                    query=keywords, 
                    limit=3
                )
                state["relevant_articles"] = relevant_articles
                logger.info(f"Retrieved {len(relevant_articles)} articles for query: {keywords}")
                
            except Exception as e:
                logger.error(f"Error retrieving articles: {e}")
                state["relevant_articles"] = []
            
            return state

        def generate_response_node(state: Dict) -> Dict:
            """Generate conversational response"""
            messages = state.get("messages", [])
            user_message = messages[-1]["content"] if messages else ""
            language = state.get("language", "french")
            articles = state.get("relevant_articles", [])
            
            # Build context from articles with source attribution
            context = ""
            sources_info = []
            if articles:
                context = "Actualités pertinentes (IMPORTANT: Ces articles sont vos seules sources d'information):\n\n"
                
                # ChromaDB returns a dict with metadatas field containing list of lists
                metadatas = articles.get('metadatas', [[]])
                if metadatas and len(metadatas) > 0:
                    article_list = metadatas[0] 
                    
                    for i, article_metadata in enumerate(article_list, 1):
                        # Extract title and content from metadata
                        title_fr = article_metadata.get('title_fr', article_metadata.get('title', ''))
                        content_fr = article_metadata.get('content_fr', '')
                        url = article_metadata.get('url', '')
                        published_at = article_metadata.get('published_at', '')
                        
                        context += f"[Source {i}] {title_fr}\n"
                        context += f"URL: {url}\n"
                        if published_at:
                            context += f"Publié le: {published_at[:10]}\n"
                        if content_fr:
                            context += f"Contenu: {content_fr[:300]}...\n\n"
                        
                        # Store source info for response formatting
                        sources_info.append({
                            'id': i,
                            'title_fr': title_fr,
                            'url': url,
                            'published_at': published_at
                        })
            
            # Store sources in state for API response
            state["sources_used"] = sources_info

            # Build conversation history for context
            conversation_history = []
            if len(messages) > 1:  # More than just the current message
                for msg in messages[:-1]:  # Exclude the current message
                    role = "Human" if msg["role"].lower() == "user" else "Assistant"
                    conversation_history.append(f"{role}: {msg['content']}")
            system_message = """Tu es un assistant conversationnel spécialisé dans l'actualité française, conçu pour aider les apprenants de français niveau B1.

RÈGLES STRICTES À SUIVRE:
- OBLIGATOIRE: Base-toi UNIQUEMENT sur les articles fournis comme sources. N'invente JAMAIS d'informations.
- OBLIGATOIRE: Cite toujours tes sources en mentionnant "[Source X]" quand tu utilises des informations d'un article.
- Si aucun article pertinent n'est fourni, dis clairement que tu n'as pas d'informations récentes sur ce sujet.
- N'affirme rien que tu ne peux pas appuyer avec les sources fournies.

Caractéristiques de ton style:
- Utilise un vocabulaire simple et accessible (niveau B1)
- Phrases claires et directes
- Évite les structures grammaticales complexes
- Sois pédagogique et engageant
- Aide les utilisateurs à comprendre l'actualité en français simple
- Encourage la discussion et pose des questions pour maintenir l'engagement
- Maintiens la cohérence avec les messages précédents de la conversation

IMPORTANT: Termine toujours ta réponse en listant les sources utilisées avec leurs titres et URLs."""

            if language == "french":
                conversation_context = ""
                if conversation_history:
                    conversation_context = f"Historique de la conversation:\n{chr(10).join(conversation_history)}\n\n"
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_message),
                    ("human", f"""{conversation_context}Contexte d'actualités:\n{context}\n\nQuestion actuelle de l'utilisateur: {user_message}
                    
                    Réponds en français B1 de manière conversationnelle et engageante, en tenant compte de l'historique de la conversation.""")
                ])
            else:
                conversation_context = ""
                if conversation_history:
                    conversation_context = f"Conversation history:\n{chr(10).join(conversation_history)}\n\n"
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful assistant discussing French news. 

STRICT RULES:
- MANDATORY: Base your responses ONLY on the provided news articles. NEVER make up information.
- MANDATORY: Always cite your sources by mentioning "[Source X]" when using information from an article.
- If no relevant articles are provided, clearly state that you don't have recent information on that topic.
- Never claim anything you cannot support with the provided sources.

Respond in English but mention French terms when relevant. Maintain consistency with previous conversation.
IMPORTANT: Always end your response by listing the sources used with their titles and URLs."""),
                    ("human", f"""{conversation_context}News context:\n{context}\n\nCurrent user question: {user_message}""")
                ])
            
            response = self.llm.invoke(prompt.format_messages())
            state["messages"].append({
                "role": "assistant",
                "content": response.content
            })
            
            return state

        def should_retrieve_articles(state: Dict) -> str:
            """Decide whether to retrieve articles based on query analysis"""
            analysis = state.get("query_analysis", {})
            intent = analysis.get("intent", "news_discussion")
            
            logger.info(f"🔀 ROUTING DECISION - Analysis: {analysis}")
            logger.info(f"🎯 Intent detected: {intent}")
            #import pdb;pdb.set_trace()
            # Only retrieve articles for news discussions
            if intent == "news_discussion":
                next_node = "retrieve_articles"
                logger.info("➡️ ROUTING TO: retrieve_articles")
                return next_node
            else:
                # Set empty articles for non-news conversations
                state["relevant_articles"] = []
                next_node = "generate_response"
                logger.info("➡️ ROUTING TO: generate_response (skipping article retrieval)")
                return next_node

        # Build the graph
        workflow = StateGraph(dict)
        
        workflow.add_node("analyze_query", analyze_query_node)
        workflow.add_node("retrieve_articles", retrieve_articles_node)
        workflow.add_node("generate_response", generate_response_node)
        
        workflow.set_entry_point("analyze_query")
        
        # Add conditional routing from analyze_query
        workflow.add_conditional_edges(
            "analyze_query",
            should_retrieve_articles,
            {
                "retrieve_articles": "retrieve_articles",
                "generate_response": "generate_response"
            }
        )
        
        workflow.add_edge("retrieve_articles", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()

    async def chat(self, message: str, conversation_id: Optional[str] = None) -> Dict:
        """Process a chat message and return response"""
        try:

            # Initialize or load conversation
            if conversation_id:
                async with db_client:
                    conversation = await db_client.get_conversation_with_messages(conversation_id)
                    if not conversation:
                        raise ValueError(f"Conversation {conversation_id} not found")
                    
                    messages = [
                        {"role": msg["role"].lower(), "content": msg["content"]}
                        for msg in conversation["messages"]
                    ]
            else:
                # Create new conversation
                async with db_client:
                    conversation = await db_client.create_conversation()
                    conversation_id = conversation["id"]
                    messages = []

            # Add user message
            messages.append({"role": "user", "content": message})

            
            # Prepare state
            state = {
                "messages": messages,
                "conversation_id": conversation_id
            }

            # Run the graph
            result = self.graph.invoke(state)
            # Save messages to database
            async with db_client:
                await db_client.add_message_to_conversation(
                    conversation_id, "USER", message
                )
                await db_client.add_message_to_conversation(
                    conversation_id, "ASSISTANT", result["messages"][-1]["content"]
                )
            
            return {
                "response": result["messages"][-1]["content"],
                "conversation_id": conversation_id,
                "relevant_articles": result.get("relevant_articles", []),
                "sources_used": result.get("sources_used", [])
            }
            
        except Exception as e:
            logger.error(f"Error in chat processing: {e}")
            raise e

    async def get_conversation_history(self, conversation_id: str) -> Dict:
        """Get conversation history"""
        try:
            async with db_client:
                conversation = await db_client.get_conversation_with_messages(conversation_id)
                if not conversation:
                    return {"error": "Conversation not found"}
                
                return {
                    "conversation_id": conversation_id,
                    "messages": [
                        {
                            "role": msg["role"].lower(),
                            "content": msg["content"],
                            "created_at": msg["createdAt"].isoformat()
                        }
                        for msg in conversation["messages"]
                    ]
                }
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {"error": "Failed to get conversation history"}