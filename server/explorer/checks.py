from saas.sdk.app.auth import User
from saas.sdk.app.base import get_current_active_user

from explorer.schemas import ExplorerRuntimeError

from fastapi import Depends


class CheckIfUser:
    def __init__(self, server):
        self.server = server

    async def __call__(self, user: User = Depends(get_current_active_user)):
        pass


class CheckProjectExists:
    def __init__(self, server):
        self.server = server

    async def __call__(self, project_id: str):
        project = self.server.get_project(project_id)
        if not project:
            raise ExplorerRuntimeError(f"Project {project_id} does not exist.")


class CheckUserHasAccess:
    def __init__(self, server):
        self.server = server

    async def __call__(self, project_id: str, user: User = Depends(get_current_active_user)):
        project = self.server.get_project(project_id)
        if not project.has_access(user):
            raise ExplorerRuntimeError(f"User '{user.login}' does not have access to project {project_id}.")


class CheckUserIsOwner:
    def __init__(self, server):
        self.server = server

    async def __call__(self, project_id: str, user: User = Depends(get_current_active_user)):
        project = self.server.get_project(project_id)
        if not project.is_owner(user):
            raise ExplorerRuntimeError(f"User '{user.login}' is not the owner of project {project_id}.")


