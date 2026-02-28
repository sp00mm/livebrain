import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates import TEMPLATES, Template, TemplateStep
from services.template_service import TemplateService
from services.database import QuestionRepository, ResourceRepository


class TestTemplateDefinitions:

    def test_all_four_templates_defined(self):
        assert set(TEMPLATES.keys()) == {'interview', 'standup', 'sales_call', 'live_debate'}

    def test_templates_have_required_fields(self):
        for key, t in TEMPLATES.items():
            assert t.key == key
            assert t.name
            assert t.description
            assert len(t.steps) > 0
            assert len(t.questions) == 5
            assert t.system_prompt_template

    def test_template_steps_have_required_fields(self):
        for t in TEMPLATES.values():
            for step in t.steps:
                assert step.key
                assert step.label
                assert step.description
                assert step.input_type in ('text', 'folder', 'text_with_url')

    def test_interview_questions(self):
        q = TEMPLATES['interview'].questions
        assert q[0] == "What's a good question to ask next based on this conversation?"
        assert q[1] == 'Are there any red flags or concerns I should dig into?'
        assert q[2] == 'How well does this candidate match the job requirements?'
        assert q[3] == 'Summarize this candidate so far'
        assert q[4] == 'What company info answers what they just asked?'

    def test_standup_questions(self):
        q = TEMPLATES['standup'].questions
        assert q[0] == "What's the technical context for what they just mentioned?"
        assert q[1] == 'Are there any blockers or dependencies I should know about?'
        assert q[2] == 'How long would that realistically take?'
        assert q[3] == 'What should I ask to get more clarity?'
        assert q[4] == "Where in the codebase is what they're talking about?"

    def test_sales_call_questions(self):
        q = TEMPLATES['sales_call'].questions
        assert q[0] == 'How does our product solve what they just mentioned?'
        assert q[1] == 'What objection are they raising and how should I handle it?'
        assert q[2] == "What's an outside-the-box angle to try here?"
        assert q[3] == 'What should I say next to move this forward?'
        assert q[4] == 'Summarize where we stand in this deal'

    def test_live_debate_questions(self):
        q = TEMPLATES['live_debate'].questions
        assert q[0] == 'Counter their last argument'
        assert q[1] == 'Is what they just said accurate?'
        assert q[2] == "What's my strongest point right now?"
        assert q[3] == 'What weak points do they have?'
        assert q[4] == 'Summarize the debate so far'


class TestTemplateService:

    def test_create_brain_from_template(self, db):
        service = TemplateService(db)
        brain = service.create_brain_from_template('interview')

        assert brain.name == 'Interview'
        assert brain.template_type == 'interview'
        assert brain.system_prompt

        questions = QuestionRepository(db).get_by_brain(brain.id)
        assert len(questions) == 5
        assert questions[0].position == 0
        assert questions[4].position == 4

    def test_create_brain_with_empty_step_values(self, db):
        service = TemplateService(db)
        brain = service.create_brain_from_template('sales_call', step_values={})

        assert brain.name == 'Sales Call'
        assert brain.template_type == 'sales_call'

        questions = QuestionRepository(db).get_by_brain(brain.id)
        assert len(questions) == 5

    def test_system_prompt_formatting(self, db):
        service = TemplateService(db)
        brain = service.create_brain_from_template('interview', step_values={
            'job_description': 'Senior Python Developer',
            'resume': 'Jane Doe, 10 years experience',
        })

        assert 'Senior Python Developer' in brain.system_prompt
        assert 'Jane Doe, 10 years experience' in brain.system_prompt

    def test_system_prompt_empty_values(self, db):
        service = TemplateService(db)
        brain = service.create_brain_from_template('live_debate')

        assert '{topic}' not in brain.system_prompt
        assert '{position}' not in brain.system_prompt

    def test_folder_step_creates_resource(self, db):
        service = TemplateService(db)
        brain = service.create_brain_from_template('standup', step_values={
            'codebase': '/path/to/project',
        })

        resources = ResourceRepository(db).get_by_brain(brain.id)
        assert len(resources) == 1
        assert resources[0].path == '/path/to/project'
        assert resources[0].name == 'Codebase'

    def test_all_templates_create_successfully(self, db):
        service = TemplateService(db)
        for key in TEMPLATES:
            brain = service.create_brain_from_template(key)
            assert brain.id
            assert brain.template_type == key
