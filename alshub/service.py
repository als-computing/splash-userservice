
from enum import Enum
import logging
import ssl
from typing import List
from httpx import AsyncClient
from starlette.config import Config
from datetime import datetime
from zoneinfo import ZoneInfo

from alshub.config.beamline_admins import ADMINS
from splash_userservice.models import User, V2UserEsaf, V2UserGroupDetails
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

    async def get_user(self, id: str, id_type: IDType=IDType.orcid, fetch_groups=True) -> User:
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

        groups = set()
        async with AsyncClient(base_url=ALSHUB_BASE, timeout=10.0) as alsusweb_client:
            # query for user information
            if id_type == IDType.email:
                q_param = "em"
            else:
                q_param = "or"
            url = f"{ALSHUB_PERSON}/?{q_param}={id}"
            full_url = f"{ALSHUB_BASE}/{url}"
            try:
                debug('Requesting: %s', full_url)
                response = await alsusweb_client.get(url)
                debug('Response status: %s', response.status_code)
                if logger.isEnabledFor(logging.DEBUG) and response.content:
                    debug('Response body: %s', response.json())
            except Exception as e:
                raise CommunicationError(f"exception talking to {url}") from e

            if response.status_code == 404:
                raise UserNotFound(f'user {id} not found in ALSHub')
            if response.is_error:
                error = f"error getting user: {id} status code: {response.status_code} message: {response.json()}"
                logger.error(error)
                raise CommunicationError(error)

            user_response_obj = response.json()

            orcid = None
            if id_type == IDType.orcid:
                orcid = id
            else:
                orcid = user_response_obj.get('orcid')

            # add staff beamlines to groups list
            if orcid:
                beamlines = await get_staff_beamlines(alsusweb_client, orcid, user_response_obj['OrgEmail'])
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

            if not orcid:
                logging.warning(f"Asked to fetch groups but could not find ORCID for user {id} returned from ALSHub")

            if orcid:
                proposals = await get_user_proposals(alsusweb_client, orcid)
                if proposals:
                    groups.update(proposals)
        
                async with AsyncClient(base_url=ESAF_BASE, timeout=10.0) as esaf_client:
                    esafs = await get_user_esafs(esaf_client, orcid)
                    esaf_ids = {esaf["ProposalFriendlyId"] for esaf in esafs}
                    if esaf_ids:
                        groups.update(esaf_ids)

            return User(**{
                "uid": user_response_obj.get('LBNLID'),
                "given_name": user_response_obj.get('FirstName'),
                "family_name": user_response_obj.get('LastName'),
                "current_institution": user_response_obj.get('Institution'),
                "current_email": user_response_obj.get('OrgEmail'),
                "orcid": user_response_obj.get('orcid'),
                "groups": list(groups)
            })

    
    async def v2_get_user_groupdetails(self, orcid: str) -> V2UserGroupDetails:
        """Return a V2UserGroupDetails object. Makes several calls to ALSHub to assemble user info,
        beamline membership and proposal info, which is used to populate group names,
        proposals, esafs, and beamlines.

        Parameters
        ----------
        orcid : str
            User's orcid

        Returns
        -------
        V2UserGroupDetails
            V2UserGroupDetails instance populated with info from ALSHub requests
        """
        async with AsyncClient(base_url=ALSHUB_BASE, timeout=10.0) as alsusweb_client:
            # query for user information
            url = f"{ALSHUB_PERSON}/?or={orcid}"
            full_url = f"{ALSHUB_BASE}/{url}"
            try:
                debug('Requesting: %s', full_url)
                response = await alsusweb_client.get(url)
                debug('Response status: %s', response.status_code)
                if logger.isEnabledFor(logging.DEBUG) and response.content:
                    debug('Response body: %s', response.json())
            except Exception as e:
                raise CommunicationError(f"exception talking to {url}") from e

            if response.status_code == 404:
                raise UserNotFound(f'user {id} not found in ALSHub')
            if response.is_error:
                error = f"error getting user: {id} status code: {response.status_code} message: {response.json()}"
                logger.error(error)
                raise CommunicationError(error)

            user_response_obj = response.json()

            # fetch staff beamlines
            beamlines = await get_staff_beamlines(alsusweb_client, orcid, user_response_obj['OrgEmail'])
            groups = set(beamlines)

            proposals = await get_user_proposals(alsusweb_client, orcid)
            if proposals:
                groups.update(proposals)

            esafs=[]
            async with AsyncClient(base_url=ESAF_BASE, timeout=10.0) as esaf_client:
                esaf_objects = await get_user_esafs(esaf_client, orcid)
                if esaf_objects:
                    esaf_ids = {esaf["ProposalFriendlyId"] for esaf in esaf_objects}
                    groups.update(esaf_ids)
                    for esaf in esaf_objects:

                        roles = []
                        if "PI" in esaf:
                            if "Orcid" in esaf["PI"] and esaf["PI"]["Orcid"] == orcid:
                                roles.append("pi")
                        if "ExpLead" in esaf:
                            if "Orcid" in esaf["ExpLead"] and esaf["ExpLead"]["Orcid"] == orcid:
                                roles.append("explead")
                        if "Participants" in esaf:
                            for participant in esaf["Participants"]:
                                if "Orcid" in participant and participant["Orcid"] == orcid:
                                    roles.append("participant")
                                    break

                        earliest_start = None
                        latest_end = None
                        if "ScheduledEvents" in esaf:
                            for event in esaf["ScheduledEvents"]:
                                if "StartDate" in event:
                                    start = parse_esaf_date(event["StartDate"] or "")
                                    if start and ((earliest_start is None) or (start < earliest_start)):
                                        earliest_start = start
                                if "EndDate" in event:
                                    end = parse_esaf_date(event["EndDate"] or "")
                                    if end and ((latest_end is None) or (end > latest_end)):
                                        latest_end = end
                                        pass
                        
                        earliest_start_field = earliest_start.isoformat() if earliest_start else None
                        latest_end_field = latest_end.isoformat() if latest_end else None

                        esaf_entry = V2UserEsaf(
                            roles=roles,
                            id=esaf.get("EsafFriendlyId"),
                            title=esaf.get("Title"),
                            proposal_id=esaf.get("ProposalFriendlyId"),
                            beamline_id=esaf.get("Beamline"),
                            earliest_start=earliest_start_field,
                            latest_end=latest_end_field
                        )
                        esafs.append(esaf_entry)  

            return V2UserGroupDetails(
                uid=user_response_obj.get('LBNLID') or None,
                given_name=user_response_obj.get('FirstName') or None,
                family_name=user_response_obj.get('LastName') or None,
                current_institution=user_response_obj.get('Institution') or None,
                current_email=user_response_obj.get('OrgEmail') or None,
                orcid=orcid,
                groups=list(groups),
                beamlines=list(beamlines),
                proposals=list(proposals) if proposals else [],
                esafs=esafs
            )


def parse_esaf_date(date_str: str) -> datetime | None:
    """Parse a date string from ALS ESAF data into a datetime object.
    The expected format is 'MM/DD/YYYY'. If parsing fails, None is returned.

    Parameters
    ----------
    date_str : str
        Date string in 'MM/DD/YYYY' format.

    Returns
    -------
    datetime
        Parsed datetime object or None if parsing fails.
    """
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    except ValueError:
        return None


async def get_user_proposals(client, orcid):
    url = f"{ALSHUB_PROPOSALBY}/?or={orcid}"
    full_url = f"{ALSHUB_BASE}/{url}"
    debug('Requesting: %s', full_url)
    response = await client.get(url)
    debug('Response status: %s', response.status_code)
    if response.is_error:
        info('error getting user proposals: %s status code: %s message: %s',
             orcid,
             response.status_code,
             response.json())
        return {}
    else:
        proposal_response_obj = response.json()
        debug('Response body: %s', proposal_response_obj)
        proposals = proposal_response_obj.get('Proposals')
        if not proposals:
            info('no proposals for orcid: %s', orcid)
            return []
        else:
            info('get_user userinfo for orcid: %s proposals: %s', 
                 orcid,
                 str(proposals))

            return {proposal_id for proposal_id in proposals}


async def get_user_esafs(client, orcid):
    url = f"{ESAF_INFO}/?or={orcid}"
    full_url = f"{ESAF_BASE}/{url}"
    debug('Requesting: %s', full_url)
    response = await client.get(url)
    debug('Response status: %s', response.status_code)
    if response.is_error:
        info('error getting user esafs: %s status code: %s message: %s',
             orcid,
             response.status_code,
             response.json())
        return []

    esafs = response.json()
    debug('Response body: %s', esafs)
    if not esafs or len(esafs) == 0:
        info('no proposals for orcid: %s', orcid)
        return []

    debug('get_user userinfo for orcid: %s proposals: %s', 
            orcid,
            str(esafs))
    return esafs


async def get_staff_beamlines(ac: AsyncClient, orcid: str, email: str) -> List[str]:
    url = f"{ALSHUB_PERSON_ROLES}/?or={orcid}"
    full_url = f"{ALSHUB_BASE}/{url}"
    debug('Requesting: %s', full_url)
    response = await ac.get(url)
    debug('Response status: %s', response.status_code)  
    # ADMINS are a list maintained in a python to add users to groups even if they're not maintained in 
    # ALSHub
    beamlines = set()
    if email and ADMINS and (email in ADMINS):
        beamlines.update(ADMINS.get(email))
    if response.is_error:
        info(f"error asking ALHub for staff roles {orcid}")
        return beamlines
    if response.content:
        response_data = response.json()
        debug('Response body: %s', response_data)
        beamline_roles = response_data.get("Beamline Roles")
        if beamline_roles:
            alshub_beamlines = alshub_roles_to_beamline_groups(
                                beamline_roles,
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
