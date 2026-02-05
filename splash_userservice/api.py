
import logging
import sys
from typing import List

from fastapi import Depends, FastAPI, Security
from fastapi.exceptions import HTTPException
from fastapi.security.api_key import APIKeyQuery, APIKeyCookie, APIKeyHeader, APIKey
from pydantic import BaseModel, Field
from starlette.config import Config
from starlette.status import HTTP_403_FORBIDDEN
from splash_userservice.models import (
    User,
    UniqueId,
    V2UserGroupDetails
)
from splash_userservice.service import CommunicationError, IDType, UserService, UserNotFound


API_KEY_NAME = "api_key"
QUERY_USERs_API = 'query_users'
config = Config(".env")
API_KEY = config("API_KEY", cast=str, default="")

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_cookie = APIKeyCookie(name=API_KEY_NAME, auto_error=False)


async def get_api_key_from_request(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header),
    api_key_cookie: str = Security(api_key_cookie)
):

    if api_key_query:
        return api_key_query
    elif api_key_header:
        return api_key_header
    elif api_key_cookie:
        return api_key_cookie
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials, missing APIKey"
        )


class GroupSummary(BaseModel):
    group_id: UniqueId
    group_name: str


# Response Models
class GetUsersGroupsResponse(BaseModel):
    groups: List[GroupSummary] = Field(description="list of group IDs and names")


logger = logging.getLogger("users")
app = FastAPI()


@app.on_event("startup")
def startup():
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)


# do this slightly complicated thing to make dependency injection work
# and make unit tests easier
this = sys.modules[__name__]
this.service = {}


def get_service() -> UserService:
    if not this.service:
        from alshub.service import ALSHubService
        this.service = ALSHubService()
    return this.service


@app.get("/api/v1/users/{id}/{id_type}")
async def get_user(
        id: str,
        id_type: IDType,
        fetch_groups: bool = False,
        user_service: UserService = Depends(get_service),
        api_key: APIKey = Depends(get_api_key_from_request)) -> User:

    await validate_api_key(api_key)
    logger.info(f"Received request for {id} and {id_type}")
    try:
        return await user_service.get_user(id, id_type)
    except UserNotFound as e:
        raise HTTPException(404, detail=e.args[0]) from e
    except CommunicationError as e:
        logger.error("Exception in service", e.args[0])
        raise HTTPException(500) from e


@app.get("/api/v2/users/orcid/{orcid}/groupdetails")
async def v2_get_user_groupdetails(
        orcid: str,
        user_service: UserService = Depends(get_service),
        api_key: APIKey = Depends(get_api_key_from_request)) -> V2UserGroupDetails:

    await validate_api_key(api_key)
    logger.info(f"Received groupdetails request for {orcid}")
    try:
        return await user_service.v2_get_user_groupdetails(orcid)
    except UserNotFound as e:
        raise HTTPException(404, detail=e.args[0]) from e
    except CommunicationError as e:
        logger.error("Exception in service", e.args[0])
        raise HTTPException(500) from e


async def validate_api_key(api_key: str):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )

# @app.get("users/{id}/groups", response_model=GetUsersGroupsResponse)
# async def get_user_groups(id: str):
#     return magrathea_group
