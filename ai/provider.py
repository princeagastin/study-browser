import json
import urllib.request
import urllib.error
import threading

class AIProvider:
    """
    A lightweight, dependency-free LLM provider.
    Defaults to local Ollama, but can be pointed to any OpenAI-compatible API.
    """
    def __init__(self, base_url="http://localhost:11434", model="llama3.1"):
        self.base_url = base_url
        self.model = model
        self.is_available = False
        self._check_connection()

    def _check_connection(self):
        """Non-blocking check to see if the local LLM server is running."""
        def _ping():
            try:
                req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        self.is_available = True
            except Exception:
                self.is_available = False
        
        threading.Thread(target=_ping, daemon=True).start()

    def generate(self, prompt: str, system_prompt: str = "", is_json: bool = False, callback=None):
        """
        Generates text. If callback is provided, runs in a background thread.
        """
        def _run():
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            }
            if is_json:
                payload["format"] = "json"
                
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate", 
                data=data, 
                headers={"Content-Type": "application/json"}
            )
            
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    text = result.get("response", "")
                    if callback:
                        callback(True, text)
                    return text
            except Exception as e:
                error_msg = f"AI Error: {str(e)}"
                if callback:
                    callback(False, error_msg)
                return error_msg

        if callback:
            threading.Thread(target=_run, daemon=True).start()
        else:
            return _run()

# Singleton instance
provider = AIProvider()