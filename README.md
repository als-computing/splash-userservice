# Purpose


This project is intended to serve as an API for Scientific User Facilities to 
have a common way to access user and group information. 

It is intended that the code in [models](./splash_userservice/models.py) and [api](./splash_userservice/api.py) would be the front-end interface, and facility-specific APIs would could then write specific code that maps to those model classes.

A fastapi server is included just because it docuemnts APIs so well. You can start it up and browse to the OpenAPI page that it generates:

    pip install -e .
    uvicorn splash_userservice.api:app

Once started, you can navigate to the page at `http://localhost:8000/docs`

## Testing

### Testing with test_user.py

The `scripts/test_user.py` script allows you to test the ALSHubService directly by querying user information:

    python scripts/test_user.py <ORCID_OR_EMAIL> [OPTIONS]

**Options:**

- `--type {orcid,email}` or `-t {orcid,email}`: Specify identifier type (default: orcid)
- `--no-groups`: Skip fetching groups, proposals, ESAFs, and beamline roles

**Examples:**

    # Fetch user by ORCID
    python scripts/test_user.py 0000-0002-1539-0297

    # Fetch user by email
    python scripts/test_user.py user@example.com --type email

    # Fetch user without groups
    python scripts/test_user.py 0000-0002-1539-0297 --no-groups

    # Get help
    python scripts/test_user.py --help

The script outputs the user information as JSON and logs all requests/responses to stderr. To see debug output (full URLs and response bodies), the logging is configured to show ALSHub service debug messages.

### Testing with test_user.sh (bash alternative)

A bash version is also available at `scripts/test_user.sh` for making direct HTTP requests:

    ./scripts/test_user.sh <ORCID> [LBNL_ID]

**Environment variables:**

- `ALSHUB_BASE`: ALSHub base URL (default: https://alsusweb.lbl.gov)
- `ESAF_BASE`: ESAF base URL (default: https://als-esaf.als.lbl.gov)
- `INSECURE_TLS`: Set to false for strict TLS verification (default: true for insecure)
- `ORCID_ID`: Override ORCID (default: 0000-0000-0000-0000)
- `SKIP_LBNL_REQUIRED_CALLS`: Skip proposals/ESAF calls if LBNLID not found

This project in a very early stage. Te [NSLS-II Scipy Cookiecutter](https://github.com/NSLS-II/scientific-python-cookiecutter) was used to start the project, but much is not yet being taken advantage of (especially documentation).
