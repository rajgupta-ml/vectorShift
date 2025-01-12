import base64
import httpx
import json
from datetime import datetime
from typing import Dict, List
from fastapi import HTTPException, status, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis
CLIENT_ID: str = 'e589022d-98b0-4001-a1cc-ccc373156631'
CLIENT_SECRET : str = "00655da8-9bc7-44e8-b294-7ac5610d1feb"
BASE_AUTHORIZATION_URL : str = "https://app.hubspot.com/oauth/authorize"
BASE_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
REDIRECT_URI : str = "http://localhost:8000/integrations/hubspot/oauth2callback"
SCOPE = ["oauth", "crm.objects.contacts.read"]
# Authorization function
async def authorize_hubspot(user_id, org_id):
    # Create a state object with user_id and org_id
    state_data: Dict[str, str] = {
        "user_id": user_id,
        "org_id": org_id,
    }

    # Convert the state object to JSON and then encode it in base64
    state_json = json.dumps(state_data)
    state_base64 = base64.urlsafe_b64encode(state_json.encode()).decode()

    params: Dict[str, str] = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPE),
        "state": state_base64  # Store the base64 encoded state
    }
    combined_query = urlencode(params)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', state_base64, expire=600)
    return f'{BASE_AUTHORIZATION_URL}?{combined_query}'

# OAuth callback function
async def oauth2callback_hubspot(request: Request):
    code = request.query_params.get("code")
    state_base64 = request.query_params.get("state")

    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")

    # Validate required parameters
    if not state_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state parameter"
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code parameter"
        )
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HubSpot OAuth error: {error_description or 'Unknown error'}"
        )

    # Decode the base64 state to retrieve user_id and org_id
    try:
        state_json = base64.urlsafe_b64decode(state_base64).decode()
        state_data = json.loads(state_json)
        user_id = state_data.get("user_id")
        org_id = state_data.get("org_id")
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    # Retrieve and validate state from Redis
    state_date = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if state_date.decode("utf-8") != state_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State mismatch, possible CSRF attack"
        )

    # Get access token
    try:
        access_data = await tokenGeneration(code)
    except HTTPException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Token generation failed: {e.detail}"
        )

    # Clean up Redis and store access data
    await delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
    await add_key_value_redis(f'hubspot_token:{org_id}:{user_id}', json.dumps(access_data), expire=access_data.get("expires_in"))
    
    # Close window HTML script
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_token:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    await delete_key_redis(f'hubspot_token:{org_id}:{user_id}')

    return credentials

# Function to create Integration Item metadata from HubSpot API response
async def create_integration_item_metadata_object(response_json: Dict) -> List[IntegrationItem]:
    try:
        if "results" not in response_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'results' in response"
            )

        integration_items = []

        # Loop through the contacts in the response to create integration items
        for contact in response_json["results"]:
            contact_properties = contact.get("properties", {})
            email_property = contact_properties.get("email")
            firstname_property = contact_properties.get("firstname")
            lastname_property = contact_properties.get("lastname")

            # Check if essential properties are present
            if not email_property or not firstname_property:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing email or firstname properties"
                )

            # Create the integration item with the data
            integration_item = IntegrationItem(
                id=str(contact.get("id")),
                name=f"{firstname_property} {lastname_property if lastname_property else ''}".strip(),
                type="contact",  # Assumed type is 'contact', modify if needed
                url=f"mailto:{email_property}",  # Assuming URL is email link
                creation_time=datetime.strptime(contact_properties.get("createdate"), "%Y-%m-%dT%H:%M:%S.%fZ"),
                last_modified_time=datetime.strptime(contact_properties.get("lastmodifieddate"), "%Y-%m-%dT%H:%M:%S.%fZ"),
                visibility=True  # Assuming visibility is true, adjust as needed
            )

            integration_items.append(integration_item)

        return integration_items

    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing expected key in response: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating integration item: {str(e)}"
        )

# Function to get HubSpot items using the provided credentials
async def get_items_hubspot(credentials: str ):
    try:
        creds = json.loads(credentials)

        if "access_token" not in creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token found in credentials"
            )

        access_token = creds["access_token"]

        url = f"https://api.hubapi.com/crm/v3/objects/contacts"

        # Make the GET request to HubSpot API
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})

        # Check if the response is successful
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"HubSpot API request failed: {response.status_code} - {response.text}"
            )

        # Parse JSON response
        response_json = response.json()

        # Call the function to create integration items metadata from the response
        integration_items = await create_integration_item_metadata_object(response_json)

        return integration_items

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Request to HubSpot API failed: {str(e)}"
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decode JSON response"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving HubSpot items: {str(e)}"
        )

# Token generation function
async def tokenGeneration(code: str):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    # Make an asynchronous POST request to get the token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(BASE_TOKEN_URL, data=payload)

        # Check response status
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"HubSpot token endpoint returned an error: {response.status_code} - {response.text}"
            )

        # Parse and return token data
        try:
            token_data = response.json()
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decode JSON response from HubSpot token endpoint"
            )

        # Ensure the expected fields exist in the response
        if "access_token" not in token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access token not found in HubSpot response"
            )

        return token_data

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while trying to connect to HubSpot: {str(e)}"
        )
