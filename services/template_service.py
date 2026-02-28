import urllib.request
import html2text

from .llm.service import LLMService
from .llm.interfaces import Message


class TemplateService:
    def __init__(self, llm: LLMService):
        self._llm = llm

    def generate_from_url(self, url: str) -> str:
        req = urllib.request.Request(url, headers={'User-Agent': 'LiveBrain/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        converter = html2text.HTML2Text()
        converter.ignore_links = True
        converter.ignore_images = True
        text = converter.handle(html)[:8000]

        response = self._llm.complete(
            [Message(role='user', content=text)],
            system_prompt=(
                'Based on the following webpage content, write a clean, concise '
                'description of the product or company. Focus on what they do, '
                'who they serve, and their key value proposition. '
                'Write 2-3 short paragraphs. No markdown formatting.'
            )
        )
        return response.text
