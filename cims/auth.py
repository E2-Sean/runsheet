from django.contrib.auth.backends import RemoteUserBackend
class ProxyRemoteUserBackend(RemoteUserBackend):
    def clean_username(self, username):
        if username and "\\" in username:
            username = username.split("\\", 1)[1]
        return username.lower() if username else username
