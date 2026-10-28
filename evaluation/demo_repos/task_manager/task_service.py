from database import save_task
from notification import notify_user


def create_task(user, task):
    save_task(user, task)
    notify_user(user, task)


def delete_task(task_id):
    print("Deleting task", task_id)
