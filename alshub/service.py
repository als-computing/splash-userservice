
from enum import Enum
import logging
import ssl
from typing import List
from httpx import AsyncClient
from starlette.config import Config

from alshub.config.beamline_admins import ADMINS
from splash_userservice.models import User
from splash_userservice.service import IDType, UserService, UserNotFound, CommunicationError

config = Config(".env")
ALSHUB_BASE = config.get("ALSHUB_BASE", cast=str, default="https://alsusweb.lbl.gov")

ALSHUB_PERSON = "ALSGetPerson"
ALSHUB_PROPOSAL = "ALSUserProposals"
ALSHUB_PROPOSALBY = "ALSGetProposalsBy"
ALSHUB_PERSON_ROLES = "ALSGetPersonRoles"

ALSHUB_APPROVAL_ROLES = ["Scientist"]

ESAF_BASE = config.get("ESAF_BASE", cast=str, default="https://als-esaf.als.lbl.gov")
ESAF_INFO = "EsafInformation/GetESAF"

logger = logging.getLogger("users.alshub")

context = ssl.create_default_context()
context.load_verify_locations(cafile="./incommonrsaca.pem")


def info(log, *args):
    if logger.isEnabledFor(logging.INFO):
        logger.info(log, *args)


def debug(log, *args):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(log, *args)


class BeamlineRoles(str, Enum):
    scientist = "Scientist"
    satisfaction_survey = "Satisfaction Survey"
    scheduler = "Scheduler"
    beamline_staff = "Beamline Staff"
    experiment_authorization = "Experiment Authorization"


class ALSHubService(UserService):
    """Implementation of splash_userservice backed by http calls to ALSHub

    Parameters
    ----------
    splash_userservice : [type]
        [description]
    """
    is_orcid_sandbox = False

    def __init__(self) -> None:
        super().__init__()

    async def get_user(self, id: str, id_type: IDType, fetch_groups=True) -> User:
        """Return a user object from ALSHub. Makes several calls to ALSHub to assemble user info,
        beamline membership and proposal info, which is used to populate group names.

        Parameters
        ----------
        orcid : str
            User's orcid

        Returns
        -------
        User
            User instance populate with info from ALSHub requests
        """

        user_lb_id = None
        groups = set()
        async with AsyncClient(base_url=ALSHUB_BASE, verify=context, timeout=10.0) as alsusweb_client:
            # query for user information
            if id_type == IDType.email:
                q_param = "em"
            else:
                q_param = "or"
            try:
                response = await alsusweb_client.get(f"{ALSHUB_PERSON}/?{q_param}={id}")
            except Exception as e:
                raise CommunicationError(f"exception talking to {ALSHUB_PERSON}/?{q_param}={id}") from e

            if response.status_code == 404:
                raise UserNotFound(f'user {id} not found in ALSHub')
            if response.is_error:
                info('error getting user: %s status code: %s message: %s',
                     id,
                     response.status_code, response.json())
                return None

            user_response_obj = response.json()
            user_lb_id = user_response_obj.get('LBNLID')
            if not user_lb_id:
                raise UserNotFound(f'user {id} not found in ALSHub or could not communicate')
            info('get_user userinfo for orcid: %s  lbid: %s',
                 id,
                 user_lb_id)

            # add staff beamlines to groups list
            # if id_type == IDType.email:
            beamlines = await get_staff_beamlines(alsusweb_client, id, user_response_obj['OrgEmail'])
            if beamlines:
                groups.update(beamlines)
            if not fetch_groups:
                return User(**{
                    "uid": user_response_obj.get('LBNLID'),
                    "given_name": user_response_obj.get('FirstName'),
                    "family_name": user_response_obj.get('LastName'),
                    "current_institution": user_response_obj.get('Institution'),
                    "current_email": user_response_obj.get('OrgEmail'),
                    "orcid": user_response_obj.get('orcid')
                })
            proposals = await get_user_proposals(alsusweb_client, user_lb_id)
            if proposals:
                groups.update(proposals)
    
            async with AsyncClient(base_url=ESAF_BASE, verify=context, timeout=10.0) as esaf_client:
                esafs = await get_user_esafs(esaf_client, user_lb_id)
                if esafs:
                    groups.update(esafs)

            return User(**{
                "uid": user_response_obj.get('LBNLID'),
                "given_name": user_response_obj.get('FirstName'),
                "family_name": user_response_obj.get('LastName'),
                "current_institution": user_response_obj.get('Institution'),
                "current_email": user_response_obj.get('OrgEmail'),
                "orcid": user_response_obj.get('orcid'),
                "groups": list(groups)
            })


async def get_user_proposals(client, lbl_id):
    response = await client.get(f"{ALSHUB_PROPOSALBY}/?lb={lbl_id}")
    if response.is_error:
        info('error getting user proposals: %s status code: %s message: %s',
             lbl_id,
             response.status_code,
             response.json())
        return {}
    else:
        proposal_response_obj = response.json()
        proposals = proposal_response_obj.get('Proposals')
        if not proposals:
            info('no proposals for lbnlid: %s', lbl_id)
            return []
        else:
            info('get_user userinfo for lblid: %s proposals: %s', 
                 lbl_id,
                 str(proposals))

            return {proposal_id for proposal_id in proposals}


async def get_user_esafs(client, lbl_id):
    response = await client.get(f"{ESAF_INFO}/?lb={lbl_id}")
    if response.is_error:
        info('error getting user esafs: %s status code: %s message: %s',
             lbl_id,
             response.status_code,
             response.json())
    else:
        esafs = response.json()
        if not esafs or len(esafs) == 0:
            info('no proposals for lbnlid: %s', lbl_id)
        else:
            debug('get_user userinfo for lblid: %s proposals: %s', 
                  lbl_id,
                  str(esafs))

            return {esaf["ProposalFriendlyId"] for esaf in esafs}


async def get_staff_beamlines(ac: AsyncClient, orcid: str, email: str) -> List[str]:
    response = await ac.get(f"{ALSHUB_PERSON_ROLES}/?or={orcid}")  
    # ADMINS are a list maintained in a python to add users to groups even if they're not maintained in 
    # ALSHub
    beamlines = set()
    if ADMINS:
        beamlines.update(ADMINS[email])
    if response.is_error:
        info(f"error asking ALHub for staff roles {orcid}")
        return beamlines
    if response.content:
        alshub_beamlines = alshub_roles_to_beamline_groups(
                            response.json()["Beamline Roles"],
                            ALSHUB_APPROVAL_ROLES)
        beamlines |= set(alshub_beamlines)
        return beamlines
    else:
        info(f"ALSHub returned no content for roles {orcid}. So no roles found")
        return beamlines


def alshub_roles_to_beamline_groups(beamline_roles: List, approval_roles: List) -> List[str]:
    """
        ALSHub has a kinda funky structure for reporting beamline roles:
        {
                "FirstName": "Zaphod",
                "LastName": "Beabelbrox",
                "ORCID": "0000-0002-1817-0042X",
                "Beamline Roles": [
                    {
                        "beamline_id": [
                            "Scientist",
                            "Beamline Usage",
                            "Satisfaction Survey",
                            "Scheduler",
                            "Beamline Staff",
                            "Experiment Authorization",
                            "RAC Beamline Admin"
                        ]
                    }
                ]
            }
        This task here is to report beamlines where the user is a Scientist on the beamline
    """
    accessable_beamlines = []
    if beamline_roles:
        for beamline_role in beamline_roles:
            beamline_id = list(beamline_role.keys())[0]
            for approval_role in approval_roles:
                if approval_role in beamline_role[beamline_id]:
                    accessable_beamlines.append(list(beamline_role.keys())[0])
    return accessable_beamlines
