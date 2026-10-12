from browser.sync_client import StudyBrowseSync

sync = StudyBrowseSync()

token = input("Paste your login access token: ").strip()
sync.set_token(token)

print("\nGetting bookmarks...")
result = sync.get_bookmarks()

print(result)