from models import Brain, Question, Resource, ResourceType
from services.database import Database, BrainRepository, QuestionRepository, ResourceRepository
from services.llm import LLMService
from templates import TEMPLATES


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

    def _build_system_prompt(self, template, step_values: dict) -> str:
        prompt = template.system_prompt_template
        for step in template.steps:
            placeholder = '{' + step.key + '}'
            if placeholder in prompt:
                value = step_values.get(step.key, '')
                prompt = prompt.replace(placeholder, value)
        return prompt
