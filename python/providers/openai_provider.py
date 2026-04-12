from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = 'gpt-4o', endpoint: str = 'https://api.openai.com/v1'):
        super().__init__(api_key=api_key, model=model, endpoint=endpoint.rstrip('/'))

    def generate_conversion(self, prompt: str) -> str:
        url = f"{self.endpoint}/chat/completions"
        response = self._post_json(
            url,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            },
            payload={
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.1
            }
        )

        return (
            response.get('choices', [{}])[0]
            .get('message', {})
            .get('content', '')
            .strip()
        )
