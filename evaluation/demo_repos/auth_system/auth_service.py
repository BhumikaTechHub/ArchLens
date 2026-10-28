from user_service import get_user
from database import save_login


def authenticate_user(username, password):
    user = get_user(username)

    if user and user["password"] == password:
        save_login(username)
        return True

    return False
