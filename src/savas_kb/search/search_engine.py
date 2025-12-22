"""
Search engine for the knowledge base.

Handles query processing, retrieval, and response generation.
"""

from typing import Optional
from openai import OpenAI

from ..config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    SEARCH_TOP_K,
    RERANK_TOP_K,
)
from ..models import Chunk, SearchResponse, SearchResult, SourceType
from ..storage import ChromaStore


class SearchEngine:
    """
    Main search engine for the knowledge base.

    Combines vector search with LLM-powered response generation.
    """

    def __init__(self, store: Optional[ChromaStore] = None):
        """
        Initialize the search engine.

        Args:
            store: Vector store to use. Creates default if not provided.
        """
        self.store = store or ChromaStore()
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_types: Optional[list[SourceType]] = None,
        project: Optional[str] = None,
        client: Optional[str] = None,
        generate_answer: bool = True,
    ) -> SearchResponse:
        """
        Search the knowledge base and generate a response.

        Args:
            query: The search query.
            top_k: Number of results to retrieve.
            source_types: Filter by source types.
            project: Filter by project.
            client: Filter by client.
            generate_answer: Whether to generate an LLM answer.

        Returns:
            SearchResponse with answer and source results.
        """
        top_k = top_k or SEARCH_TOP_K

        # Retrieve relevant chunks
        results = self.store.search(
            query=query,
            top_k=top_k,
            source_types=source_types,
            project=project,
            client=client,
        )

        # Generate answer if requested
        answer = ""
        sources_used = 0

        if generate_answer and results:
            # Take top results for answer generation
            top_results = results[:RERANK_TOP_K]
            answer, sources_used = self._generate_answer(query, top_results)

        return SearchResponse(
            query=query,
            answer=answer,
            results=results,
            sources_used=sources_used,
        )

    def _generate_answer(
        self,
        query: str,
        results: list[SearchResult],
    ) -> tuple[str, int]:
        """
        Generate an answer using the LLM based on retrieved chunks.

        Args:
            query: The original query.
            results: Retrieved search results.

        Returns:
            Tuple of (answer text, number of sources used).
        """
        if not results:
            return "I couldn't find any relevant information to answer your question.", 0

        # Build context from results
        context_parts = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            source_info = f"[Source {i}: {chunk.source_type.value}"
            if chunk.channel:
                source_info += f" - {chunk.channel}"
            if chunk.timestamp:
                source_info += f" - {chunk.timestamp.strftime('%Y-%m-%d')}"
            source_info += "]"

            context_parts.append(f"{source_info}\n{chunk.content}")

        context = "\n\n---\n\n".join(context_parts)

        # Generate answer
        system_prompt = """You are a helpful assistant that answers questions based on company knowledge.

Your job is to:
1. Answer the question using ONLY the provided context
2. Cite your sources by referring to [Source N] when you use information from that source
3. If the context doesn't contain enough information, say so honestly
4. Be concise but complete
5. If asked about people, projects, or decisions, provide specific details from the sources

Do not make up information. Only use what's in the context."""

        user_prompt = f"""Context from company knowledge base:

{context}

---

Question: {query}

Please answer based on the context above, citing sources where appropriate."""

        response = self.openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        answer = response.choices[0].message.content or ""
        return answer, len(results)

    def search_for_sales_prep(
        self,
        prospect_context: str,
        top_k: int = 10,
    ) -> SearchResponse:
        """
        Search for relevant experience to prepare for a sales call.

        Takes prospect context (RFP, call notes, etc.) and finds
        the most relevant past projects and experience.

        Args:
            prospect_context: Context about the prospect (RFP, notes, etc.)
            top_k: Number of results to retrieve.

        Returns:
            SearchResponse with relevant experience.
        """
        # First, extract key themes from the prospect context
        extraction_prompt = """Analyze this prospect information and extract:
1. Industry/sector
2. Key challenges or needs mentioned
3. Technologies or approaches they're interested in
4. Project type (web development, modernization, etc.)

Respond with a search query that would find relevant past experience.
Keep it concise - just the key terms and concepts."""

        response = self.openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": prospect_context},
            ],
            temperature=0.3,
            max_tokens=200,
        )

        search_query = response.choices[0].message.content or prospect_context

        # Search with the extracted query
        results = self.store.search(query=search_query, top_k=top_k)

        # Generate a sales-focused summary
        if results:
            answer = self._generate_sales_prep_answer(prospect_context, results)
        else:
            answer = "No directly relevant past experience found. Consider broadening the search."

        return SearchResponse(
            query=prospect_context[:200] + "..." if len(prospect_context) > 200 else prospect_context,
            answer=answer,
            results=results,
            sources_used=len(results),
        )

    def _generate_sales_prep_answer(
        self,
        prospect_context: str,
        results: list[SearchResult],
    ) -> str:
        """Generate a sales-focused summary of relevant experience."""
        context_parts = []
        for i, result in enumerate(results[:5], 1):
            chunk = result.chunk
            context_parts.append(f"[{i}] {chunk.content}")

        context = "\n\n".join(context_parts)

        prompt = f"""Based on the prospect context and our past experience, provide a sales prep summary.

PROSPECT CONTEXT:
{prospect_context}

OUR RELEVANT EXPERIENCE:
{context}

---

Provide:
1. Most relevant past projects to highlight (with specific details)
2. Similar challenges we've solved
3. Technologies/approaches we've used that are relevant
4. Key people who worked on similar projects (if mentioned)
5. Talking points for the call

Be specific and cite the source numbers."""

        response = self.openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )

        return response.choices[0].message.content or ""

    def search_for_1on1_prep(
        self,
        team_member_name: str,
        days_back: int = 30,
    ) -> SearchResponse:
        """
        Search for context to prepare for a 1:1 with a team member.

        Args:
            team_member_name: Name of the team member.
            days_back: How many days back to search.

        Returns:
            SearchResponse with relevant context.
        """
        # Search for mentions of this person
        query = f"{team_member_name} project work discussion standup update"

        results = self.store.search(query=query, top_k=20)

        # Filter to results that actually mention this person
        relevant_results = []
        name_lower = team_member_name.lower()
        for result in results:
            if name_lower in result.chunk.content.lower():
                relevant_results.append(result)
            elif name_lower in (result.chunk.author or "").lower():
                relevant_results.append(result)

        # Generate 1:1 prep summary
        if relevant_results:
            answer = self._generate_1on1_prep_answer(team_member_name, relevant_results[:10])
        else:
            answer = f"No recent mentions of {team_member_name} found in the knowledge base."

        return SearchResponse(
            query=f"1:1 prep for {team_member_name}",
            answer=answer,
            results=relevant_results[:10],
            sources_used=len(relevant_results[:10]),
        )

    def _generate_1on1_prep_answer(
        self,
        team_member_name: str,
        results: list[SearchResult],
    ) -> str:
        """Generate a 1:1 prep summary."""
        context_parts = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            date_str = chunk.timestamp.strftime("%Y-%m-%d") if chunk.timestamp else "unknown"
            context_parts.append(f"[{date_str}] {chunk.content}")

        context = "\n\n".join(context_parts)

        prompt = f"""Based on recent activity, prepare discussion topics for a 1:1 with {team_member_name}.

RECENT MENTIONS AND ACTIVITY:
{context}

---

Summarize:
1. Recent project involvement
2. Wins or accomplishments mentioned
3. Blockers or challenges mentioned
4. Topics worth discussing
5. Questions to ask

Focus on being helpful for a productive 1:1 conversation."""

        response = self.openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        return response.choices[0].message.content or ""
