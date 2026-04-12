from typing import Optional

from ..utils.logger import logger
from .base_provider import BaseProvider

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception as exc:
    GEMINI_AVAILABLE = False
    genai = None
    _GEMINI_IMPORT_ERROR = str(exc)


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = 'gemini-2.5-flash', endpoint: Optional[str] = None):
        super().__init__(api_key=api_key, model=model, endpoint=endpoint)
        self.enabled = GEMINI_AVAILABLE and bool(api_key)

        if self.enabled:
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(model)
        else:
            self.client = None
            error_details = f" ({_GEMINI_IMPORT_ERROR})" if '_GEMINI_IMPORT_ERROR' in globals() else ''
            logger.warning(f'Gemini provider unavailable (missing package, incompatible runtime, or API key){error_details}')

    def generate_conversion(self, prompt: str) -> str:
        if not self.client:
            raise RuntimeError('Gemini provider is not initialized')

        response = self.client.generate_content(prompt)
        return (response.text or '').strip()
