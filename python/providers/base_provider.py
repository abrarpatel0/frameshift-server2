import json
from typing import Dict, Optional
from urllib import request


class BaseProvider:
    def __init__(self, api_key: str, model: Optional[str] = None, endpoint: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint

    @staticmethod
    def _post_json(url: str, headers: Dict[str, str], payload: Dict) -> Dict:
        data = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=data, headers=headers, method='POST')
        with request.urlopen(req, timeout=60) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)

    @staticmethod
    def _extract_text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            if 'text' in value and isinstance(value['text'], str):
                return value['text']
            for nested_value in value.values():
                extracted = BaseProvider._extract_text(nested_value)
                if extracted:
                    return extracted
        if isinstance(value, list):
            for item in value:
                extracted = BaseProvider._extract_text(item)
                if extracted:
                    return extracted
        return ''
