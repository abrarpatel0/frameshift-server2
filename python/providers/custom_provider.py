from .base_provider import BaseProvider


class CustomProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = 'default-model', endpoint: str = ''):
        super().__init__(api_key=api_key, model=model, endpoint=endpoint.rstrip('/'))

    def generate_conversion(self, prompt: str) -> str:
        if not self.endpoint:
            raise RuntimeError('Custom provider endpoint is required')

        # Assume OpenAI-compatible endpoint contract for custom providers.
        url = self.endpoint
        if not url.endswith('/chat/completions'):
            url = f"{url}/chat/completions"

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
