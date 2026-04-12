from ..utils.logger import logger

OpenAIProvider = None
GeminiProvider = None
ClaudeProvider = None
CustomProvider = None

try:
    from .openai_provider import OpenAIProvider
except Exception as exc:
    logger.warning(f'OpenAI provider unavailable: {exc}')

try:
    from .gemini_provider import GeminiProvider
except Exception as exc:
    logger.warning(f'Gemini provider unavailable: {exc}')

try:
    from .claude_provider import ClaudeProvider
except Exception as exc:
    logger.warning(f'Claude provider unavailable: {exc}')

try:
    from .custom_provider import CustomProvider
except Exception as exc:
    logger.warning(f'Custom provider unavailable: {exc}')

__all__ = [
    'OpenAIProvider',
    'GeminiProvider',
    'ClaudeProvider',
    'CustomProvider',
]
