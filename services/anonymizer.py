import json

from .llm.interfaces import Message
from .llm.service import LLMService

SYSTEM_PROMPT = (
    'You are a PII detector. Find all personally identifiable information in the text '
    'and return realistic fake replacements. Keep replacements consistent and natural-sounding. '
    'Detect: names, emails, phone numbers, addresses, company names, dates of birth, '
    'social security numbers, credit card numbers, and any other PII. '
    'Return ONLY valid JSON in this exact format: '
    '{"replacements": {"original value": "fake replacement", ...}} '
    'If no PII is found, return {"replacements": {}}'
)


class Anonymizer:
    def __init__(self, llm_service: LLMService):
        self._llm = llm_service

    def anonymize(self, texts: list[str]) -> tuple[list[str], dict]:
        combined = '\n---\n'.join(texts)
        response = self._llm.complete(
            [Message(role='user', content=combined)],
            system_prompt=SYSTEM_PROMPT
        )
        replacements = json.loads(response.text).get('replacements', {})
        sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
        anonymized = []
        for text in texts:
            for key in sorted_keys:
                text = text.replace(key, replacements[key])
            anonymized.append(text)
        return anonymized, replacements
