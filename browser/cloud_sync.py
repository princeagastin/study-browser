import json
from pathlib import Path

import requests


class CloudSync:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.user = None

        self.session_file = (
            Path(__file__).resolve().parent.parent
            / "cloud_session.json"
        )

        self.load_session()

    @property
    def logged_in(self):
        return bool(self.token and self.user)

    def _headers(self):
        if not self.token:
            raise RuntimeError("Not logged in")

        return {
            "Authorization": f"Bearer {self.token}",
        }

    def login(self, username, password):
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={
                "username": username,
                "password": password,
            },
            timeout=10,
        )

        if response.status_code != 200:
            try:
                message = response.json().get(
                    "detail",
                    "Login failed",
                )
            except Exception:
                message = "Login failed"

            raise RuntimeError(message)

        data = response.json()

        self.token = data["access_token"]
        self.user = data["user"]

        self.save_session()

        return self.user

    def register(self, username, password):
        response = requests.post(
            f"{self.base_url}/api/auth/register",
            json={
                "username": username,
                "password": password,
            },
            timeout=10,
        )

        if response.status_code != 200:
            try:
                message = response.json().get(
                    "detail",
                    "Registration failed",
                )
            except Exception:
                message = "Registration failed"

            raise RuntimeError(message)

        data = response.json()

        self.token = data["access_token"]
        self.user = data["user"]

        self.save_session()

        return self.user

    def verify_session(self):
        if not self.token:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/users/me",
                headers=self._headers(),
                timeout=10,
            )

            if response.status_code != 200:
                self.logout()
                return False

            data = response.json()
            self.user = data["user"]
            self.save_session()

            return True

        except requests.RequestException:
            return False

    def save_session(self):
        if not self.token or not self.user:
            return

        data = {
            "token": self.token,
            "user": self.user,
        }

        try:
            self.session_file.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Could not save cloud session: {exc}")

    def load_session(self):
        if not self.session_file.exists():
            return

        try:
            data = json.loads(
                self.session_file.read_text(
                    encoding="utf-8"
                )
            )

            self.token = data.get("token")
            self.user = data.get("user")

        except (OSError, json.JSONDecodeError):
            self.token = None
            self.user = None

    def get_bookmarks(self):
        response = requests.get(
            f"{self.base_url}/api/bookmarks",
            headers=self._headers(),
            timeout=10,
        )

        response.raise_for_status()

        return response.json()["bookmarks"]

    def save_bookmark(self, title, url):
        response = requests.post(
            f"{self.base_url}/api/bookmarks",
            headers=self._headers(),
            json={
                "title": title,
                "url": url,
            },
            timeout=10,
        )

        response.raise_for_status()

        return response.json()["bookmark"]

    def delete_bookmark(self, bookmark_id):
        response = requests.delete(
            f"{self.base_url}/api/bookmarks/{bookmark_id}",
            headers=self._headers(),
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    def remove_bookmark_by_url(self, url):
        bookmarks = self.get_bookmarks()

        for bookmark in bookmarks:
            if bookmark["url"] == url:
                self.delete_bookmark(bookmark["id"])
                return True

        return False

    def logout(self):
        self.token = None
        self.user = None

        try:
            if self.session_file.exists():
                self.session_file.unlink()
        except OSError as exc:
            print(f"Could not remove cloud session: {exc}")