import urllib.request
from html.parser import HTMLParser

from models import Brain, Question, Resource, ResourceType
from services.database import Database, BrainRepository, QuestionRepository, ResourceRepository
from services.llm import LLMService
from services.llm.interfaces import Message
from templates import TEMPLATES


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        return ' '.join(self._parts)


class TemplateService:
    def __init__(self, db: Database, llm_service: LLMService = None):
        self._brain_repo = BrainRepository(db)
        self._question_repo = QuestionRepository(db)
        self._resource_repo = ResourceRepository(db)
        self._llm = llm_service

    def create_brain_from_template(self, template_key: str, step_values: dict = None) -> Brain:
        template = TEMPLATES[template_key]
        step_values = step_values or {}

        system_prompt = self._build_system_prompt(template, step_values)

        brain = self._brain_repo.create(Brain(
            name=template.name,
            template_type=template.key,
            system_prompt=system_prompt,
        ))

        for i, text in enumerate(template.questions):
            self._question_repo.create(Question(
                brain_id=brain.id,
                text=text,
                position=i,
            ))

        for step in template.steps:
            if step.input_type == 'folder' and step.key in step_values:
                path = step_values[step.key]
                resource = self._resource_repo.create(Resource(
                    resource_type=ResourceType.FOLDER,
                    name=step.label,
                    path=path,
                ))
                self._resource_repo.link_to_brain(resource.id, brain.id)

        return brain

    def generate_from_url(self, url: str) -> str:
        req = urllib.request.Request(url, headers={'User-Agent': 'Livebrain/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        extractor = _TextExtractor()
        extractor.feed(html)
        text = extractor.get_text()[:8000]

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

    def _build_system_prompt(self, template, step_values: dict) -> str:
        prompt = template.system_prompt_template
        for step in template.steps:
            placeholder = '{' + step.key + '}'
            if placeholder in prompt:
                value = step_values.get(step.key, '')
                prompt = prompt.replace(placeholder, value)
        return prompt
