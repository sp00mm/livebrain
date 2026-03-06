from dataclasses import dataclass, field


@dataclass
class TemplateStep:
    key: str
    label: str
    description: str
    input_type: str  # 'text', 'folder', 'text_with_url'


@dataclass
class Template:
    key: str
    name: str
    description: str
    steps: list[TemplateStep] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    system_prompt_template: str = ''
    system_context: str = ''


TEMPLATES: dict[str, Template] = {
    'interview': Template(
        key='interview',
        name='Interview',
        description='Evaluate candidates',
        steps=[
            TemplateStep(
                key='job_description',
                label='Job Description',
                description='Paste the job description or upload a PDF',
                input_type='text',
            ),
            TemplateStep(
                key='resume',
                label='Candidate Resume',
                description='Paste the resume or upload a PDF',
                input_type='text',
            ),
            TemplateStep(
                key='company_documents',
                label='Company Documents',
                description='Select a folder with HR docs, policies, etc.',
                input_type='folder',
            ),
        ],
        questions=[
            "What's a good question to ask next based on this conversation?",
            'Are there any red flags or concerns I should dig into?',
            'How well does this candidate match the job requirements?',
            'Summarize this candidate so far',
            'What company info answers what they just asked?',
        ],
        system_prompt_template=(
            'You are an expert interviewer helping evaluate a job candidate in real time. '
            'Be concise, actionable, and specific.\n\n'
            '{job_description}\n\n'
            '{resume}'
        ),
        system_context=(
            'You are helping an interviewer evaluate a job candidate in real time. '
            'Focus on assessing role fit, identifying red flags, and suggesting '
            'follow-up questions based on what the candidate says.'
        ),
    ),
    'standup': Template(
        key='standup',
        name='Stand-up',
        description='Stay sharp in standups',
        steps=[
            TemplateStep(
                key='codebase',
                label='Codebase',
                description='Select your project folder(s) to scan',
                input_type='folder',
            ),
            TemplateStep(
                key='project_docs',
                label='Project Docs',
                description='Select a folder with specs, tickets, or notes',
                input_type='folder',
            ),
        ],
        questions=[
            "What's the technical context for what they just mentioned?",
            'Are there any blockers or dependencies I should know about?',
            'How long would that realistically take?',
            'What should I ask to get more clarity?',
            'Where in the codebase is what they\'re talking about?',
        ],
        system_prompt_template=(
            'You are a technical assistant with deep knowledge of the codebase and project docs. '
            'Provide code-level insights, reference specific files, estimate timelines, '
            'and help ask smart follow-up questions. Technical but concise.'
        ),
        system_context=(
            'You are helping a developer during a team standup meeting. '
            'Reference specific files and code when possible. Provide technical '
            'insights and help track action items.'
        ),
    ),
    'sales_call': Template(
        key='sales_call',
        name='Sales Call',
        description='Close deals faster',
        steps=[
            TemplateStep(
                key='product_description',
                label='Product Description',
                description='Describe your product or generate from a URL',
                input_type='text_with_url',
            ),
            TemplateStep(
                key='prospect_profile',
                label='Prospect Profile',
                description='Describe who you\'re selling to or generate from a URL',
                input_type='text_with_url',
            ),
            TemplateStep(
                key='supporting_documents',
                label='Supporting Documents',
                description='Select a folder with contracts, case studies, pricing sheets, etc.',
                input_type='folder',
            ),
        ],
        questions=[
            'How does our product solve what they just mentioned?',
            'What objection are they raising and how should I handle it?',
            "What's an outside-the-box angle to try here?",
            'What should I say next to move this forward?',
            'Summarize where we stand in this deal',
        ],
        system_prompt_template=(
            'You are a sales coach helping close a deal in real time. '
            'Be strategic, persuasive, and honest.\n\n'
            '{product_description}\n\n'
            '{prospect_profile}'
        ),
        system_context=(
            'You are coaching a salesperson during a live customer call. '
            'Focus on objection handling, identifying buying signals, and '
            'suggesting closing strategies.'
        ),
    ),
    'live_debate': Template(
        key='live_debate',
        name='Live Debate',
        description='Win the argument',
        steps=[
            TemplateStep(
                key='topic',
                label='Topic',
                description="What's being debated?",
                input_type='text',
            ),
            TemplateStep(
                key='position',
                label='Your Position',
                description="What's your stance and why?",
                input_type='text',
            ),
            TemplateStep(
                key='research',
                label='Research',
                description='Select files or a folder with supporting evidence',
                input_type='folder',
            ),
        ],
        questions=[
            'Counter their last argument',
            'Is what they just said accurate?',
            "What's my strongest point right now?",
            'What weak points do they have?',
            'Summarize the debate so far',
        ],
        system_prompt_template=(
            'You are a sharp debate coach. You know the topic, understand the position, '
            'and have the research ready. Suggest counterarguments, fact-check claims, '
            'identify logical weaknesses, and recommend powerful responses. Quick and decisive.\n\n'
            '{topic}\n\n'
            '{position}'
        ),
        system_context=(
            'You are coaching a debater during a live debate. Fact-check claims '
            'in real time, identify logical fallacies, and suggest counterarguments.'
        ),
    ),
    'lecture': Template(
        key='lecture',
        name='Lecture',
        description='Learn more in class',
        steps=[
            TemplateStep(
                key='course_materials',
                label='Course Materials',
                description='Select a folder with slides, syllabi, textbooks, etc.',
                input_type='folder',
            ),
            TemplateStep(
                key='notes',
                label='Your Notes',
                description="Anything you want to add — topic, what you're struggling with, etc.",
                input_type='text',
            ),
        ],
        questions=[
            'Explain what they just said in simpler terms',
            'How does this connect to what was covered earlier?',
            "What's a good question to ask about this?",
            'Summarize the lecture so far',
            'What should I write down from that?',
        ],
        system_prompt_template=(
            'You are a tutor helping a student during a live lecture. '
            'Be concise and clear.\n\n'
            '{notes}'
        ),
        system_context=(
            'You are helping a student understand a lecture in real time. '
            'Simplify concepts, connect ideas, and suggest questions.'
        ),
    ),
}
