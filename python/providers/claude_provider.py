from .base_provider import BaseProvider


class ClaudeProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = 'claude-3-5-sonnet-latest', endpoint: str = 'https://api.anthropic.com/v1'):
        super().__init__(api_key=api_key, model=model, endpoint=endpoint.rstrip('/'))

    def generate_conversion(self, prompt: str) -> str:
        url = f"{self.endpoint}/messages"
        response = self._post_json(
            url,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01'
            },
            payload={
                'model': self.model,
                'max_tokens': 4096,
                'messages': [{'role': 'user', 'content': prompt}]
            }
        )

        content = response.get('content', [])
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                return (first.get('text') or '').strip()
        return ''
