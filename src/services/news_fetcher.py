import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import xml.etree.ElementTree as ET
from pydantic import BaseModel
import asyncio


class NewsArticle(BaseModel):
    title: str
    content: str
    url: str
    published_at: datetime


class BBCNewsFetcher:
    def __init__(self, rss_url: str = "https://feeds.bbci.co.uk/news/rss.xml"):
        self.rss_url = rss_url
        self.session = httpx.AsyncClient()

    async def fetch_rss_feed(self) -> List[Dict]:
        async with self.session as client:
            response = await client.get(self.rss_url)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            items = []
            
            for item in root.findall(".//item"):
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                description = item.find("description").text if item.find("description") is not None else ""
                
                items.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "description": description
                })
            
            return items

    async def fetch_article_content(self, url: str) -> str:
        try:
            async with self.session as client:
                response = await client.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # BBC specific content extraction
                content_blocks = soup.find_all('div', {'data-component': 'text-block'})
                if not content_blocks:
                    # Fallback to paragraph tags
                    content_blocks = soup.find_all('p')
                
                content = " ".join([block.get_text().strip() for block in content_blocks])
                return content
        except Exception as e:
            print(f"Error fetching content from {url}: {e}")
            return ""

    def parse_date(self, date_str: str) -> datetime:
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                return datetime.now()

    async def fetch_latest_news(self, limit: int = 10) -> List[NewsArticle]:
        rss_items = await self.fetch_rss_feed()
        articles = []
        
        tasks = []
        for item in rss_items[:limit]:
            tasks.append(self._process_article(item))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, NewsArticle):
                articles.append(result)
        
        return articles

    async def _process_article(self, item: Dict) -> NewsArticle:
        content = await self.fetch_article_content(item["link"])
        published_at = self.parse_date(item["pub_date"])
        
        return NewsArticle(
            title=item["title"],
            content=content or item["description"],
            url=item["link"],
            published_at=published_at
        )

    async def close(self):
        await self.session.aclose()