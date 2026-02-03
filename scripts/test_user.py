#!/usr/bin/env python3
"""
Test script for splash-userservice that calls ALSHubService directly.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Literal

import typer

# Add parent directory to path so we can import the service modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from alshub.service import ALSHubService
from splash_userservice.service import IDType


# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Enable debug logging only for ALSHub service
logging.getLogger('users.alshub').setLevel(logging.DEBUG)
logging.getLogger('alshub').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

app = typer.Typer()


async def test_user_async(
    user_id: str,
    id_type: Literal["orcid", "email"] = "orcid",
    fetch_groups: bool = True
) -> int:
    """
    Test the user service by fetching a user and their groups.
    
    Parameters
    ----------
    user_id : str
        User identifier (ORCID or email)
    id_type : str
        Type of identifier: 'orcid' or 'email'
    fetch_groups : bool
        Whether to fetch user groups (proposals, ESAFs, beamline roles)
    """
    service = ALSHubService()
    
    try:
        id_type_enum = IDType[id_type.lower()]
    except KeyError:
        typer.echo(f"Error: Invalid id_type '{id_type}'. Must be 'orcid' or 'email'.", err=True)
        return 1
    
    try:
        typer.echo(f"==> Fetching user: {user_id} (type: {id_type})", err=True)
        user = await service.get_user(user_id, id_type_enum, fetch_groups=fetch_groups)
        
        if user:
            # Convert User model to dict for pretty printing
            user_dict = user.dict()
            typer.echo(json.dumps(user_dict, indent=2))
            typer.echo(f"\n==> Successfully fetched user: {user.uid}", err=True)
            return 0
        else:
            typer.echo(f"Error: No user returned from service.", err=True)
            return 1
            
    except Exception as e:
        typer.echo(f"Error: {type(e).__name__}: {e}", err=True)
        logger.exception("Exception during user fetch")
        return 1


@app.command()
def main(
    user_id: str = typer.Argument(..., help="User identifier (ORCID or email)"),
    id_type: Literal["orcid", "email"] = typer.Option(
        "orcid",
        "--type",
        "-t",
        help="Type of identifier"
    ),
    no_groups: bool = typer.Option(
        False,
        "--no-groups",
        help="Don't fetch groups (proposals, ESAFs, beamlines)"
    ),
) -> None:
    """
    Test script for splash-userservice that calls ALSHubService directly.
    """
    exit_code = asyncio.run(
        test_user_async(user_id, id_type=id_type, fetch_groups=not no_groups)
    )
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
