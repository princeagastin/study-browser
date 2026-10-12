import requests


class StudyBrowseSync:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.token = None

    def set_token(self, token):
        self.token = token.strip()

    def _headers(self):
        if not self.token:
            return {}

        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def save_bookmark(self, title, url):
        response = requests.post(
            f"{self.base_url}/api/bookmarks",
            json={
                "title": title,
                "url": url,
            },
            headers=self._headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_bookmarks(self):
        response = requests.get(
            f"{self.base_url}/api/bookmarks",
            headers=self._headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def delete_bookmark(self, bookmark_id):
        response = requests.delete(
            f"{self.base_url}/api/bookmarks/{bookmark_id}",
            headers=self._headers(),
            timeout=10,
        )

        response.raise_for_status()
        return response.json()