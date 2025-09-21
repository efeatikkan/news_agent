from openai import AsyncOpenAI
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class FrenchB1Translator:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    async def translate_to_french_b1(self, text: str, content_type: str = "article") -> str:
        """
        Translate text to French B1 level (intermediate)
        B1 level characteristics:
        - Simple vocabulary (2000-3000 most common words)
        - Present, past, future tenses
        - Avoid complex grammar structures
        - Clear, direct sentences
        - Familiar topics and concrete concepts
        """
        
        system_prompt = """You are a professional translator specializing in French B1 level translations for language learners.

B1 Level Guidelines:
- Use simple, common vocabulary (avoid technical or advanced terms)
- Keep sentences clear and direct
- Use present, past simple, and future tenses primarily
- Avoid subjunctive mood and complex grammar
- Replace difficult words with simpler synonyms
- Break long sentences into shorter ones
- Focus on clarity over literary style

Your task is to translate the given text to French B1 level while maintaining the original meaning and keeping it engaging for intermediate French learners."""

        user_prompt = f"""Translate this {content_type} to French B1 level:

{text}

Remember to:
1. Use vocabulary appropriate for B1 learners
2. Keep sentences simple and clear
3. Maintain the original meaning
4. Make it engaging for language learners"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Translation error: {e}")
            return f"Translation error: {str(e)}"

    async def translate_title(self, title: str) -> str:
        """Translate a news title to French B1 level"""
        return await self.translate_to_french_b1(title, "news title")

    async def translate_content(self, content: str) -> str:
        """Translate news content to French B1 level"""
        # Split long content into chunks if necessary
        if len(content) > 3000:
            chunks = self._split_content(content, 3000)
            translated_chunks = []
            
            for chunk in chunks:
                translated_chunk = await self.translate_to_french_b1(chunk, "news article")
                translated_chunks.append(translated_chunk)
            
            return " ".join(translated_chunks)
        else:
            return await self.translate_to_french_b1(content, "news article")

    def _split_content(self, content: str, max_length: int) -> list:
        """Split content into chunks at sentence boundaries"""
        sentences = content.split('. ')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            if current_length + sentence_length > max_length and current_chunk:
                chunks.append('. '.join(current_chunk) + '.')
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length + 2  # +2 for '. '
        
        if current_chunk:
            chunks.append('. '.join(current_chunk))
        
        return chunks

    async def get_b1_vocabulary_explanation(self, word: str) -> str:
        """Get a B1-level explanation of a French word"""
        prompt = f"""Explain the French word "{word}" in simple French suitable for B1 learners. 
        Include:
        1. Simple definition
        2. Example sentence
        3. Any common synonyms
        
        Keep the explanation in French B1 level."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"Erreur d'explication: {str(e)}"