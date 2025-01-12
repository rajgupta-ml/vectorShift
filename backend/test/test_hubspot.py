# test/test_hubspot.py

from urllib.parse import urlencode
import pytest
from unittest.mock import AsyncMock, Mock, patch
import json
import base64
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Update import to match your project structure
from integrations.hubspot import (
    authorize_hubspot,
    oauth2callback_hubspot,
    get_hubspot_credentials,
    create_integration_item_metadata_object,
    get_items_hubspot,
    tokenGeneration,
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI
)

@pytest.fixture
def mock_redis():
    """Fixture for mocking Redis client"""
    with patch('integrations.hubspot.add_key_value_redis', new_callable=AsyncMock) as add_mock, \
         patch('integrations.hubspot.delete_key_redis', new_callable=AsyncMock) as delete_mock, \
         patch('integrations.hubspot.get_value_redis', new_callable=AsyncMock) as get_mock:
        yield {
            'add': add_mock,
            'delete': delete_mock,
            'get': get_mock
        }

@pytest.fixture
def mock_httpx_client():
    """Fixture for mocking HTTPX client"""
    with patch('httpx.AsyncClient') as mock:
        client = AsyncMock()
        mock.return_value.__aenter__.return_value = client
        mock.return_value.__aexit__.return_value = None
        yield client

@pytest.mark.asyncio
async def test_authorize_hubspot(mock_redis):
    # Test data
    user_id = "test_user"
    org_id = "test_org"
    
    # Execute function
    result = await authorize_hubspot(user_id, org_id)

    # Assertions
    assert "app.hubspot.com/oauth/authorize" in result
    assert CLIENT_ID in result
    assert urlencode({"redirect_uri": REDIRECT_URI}).split('=')[1] in result  # Check the encoded redirect_uri

@pytest.mark.asyncio
async def test_oauth2callback_success(mock_redis):
    # Create mock request
    state_data = {
        "user_id": "test_user",
        "org_id": "test_org"
    }
    state_base64 = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    mock_request = Mock()
    mock_request.query_params = {
        "code": "test_code",
        "state": state_base64
    }
    
    # Mock Redis return value
    mock_redis['get'].return_value = state_base64.encode()
    
    # Mock token generation
    mock_token_data = {
        "access_token": "test_token",
        "expires_in": 3600
    }
    
    with patch('integrations.hubspot.tokenGeneration', new_callable=AsyncMock) as mock_token:
        mock_token.return_value = mock_token_data
        response = await oauth2callback_hubspot(mock_request)
        
        assert isinstance(response, HTMLResponse)
        assert "window.close();" in response.body.decode()
        mock_redis['delete'].assert_called_once()
        mock_redis['add'].assert_called_once()

@pytest.mark.asyncio
async def test_oauth2callback_missing_code():
    mock_request = Mock()
    mock_request.query_params = {
        "state": "test_state"
    }
    
    with pytest.raises(HTTPException) as exc_info:
        await oauth2callback_hubspot(mock_request)
    
    assert exc_info.value.status_code == 400
    assert "Missing code parameter" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_get_hubspot_credentials_success(mock_redis):
    # Test data
    user_id = "test_user"
    org_id = "test_org"
    mock_credentials = {
        "access_token": "test_token",
        "expires_in": 3600
    }
    
    # Mock Redis return value
    mock_redis['get'].return_value = json.dumps(mock_credentials).encode()
    
    # Execute function
    result = await get_hubspot_credentials(user_id, org_id)
    
    # Assertions
    assert result == mock_credentials
    mock_redis['delete'].assert_called_once_with(f'hubspot_token:{org_id}:{user_id}')

@pytest.mark.asyncio
async def test_create_integration_item_metadata_success():
    mock_response = {
        "results": [{
            "id": "123",
            "properties": {
                "email": "test@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "createdate": "2024-01-01T12:00:00.000Z",
                "lastmodifieddate": "2024-01-01T12:00:00.000Z"
            }
        }]
    }
    
    result = await create_integration_item_metadata_object(mock_response)
    
    assert len(result) == 1
    item = result[0]
    assert item.id == "123"
    assert item.name == "John Doe"
    assert item.type == "contact"
    assert item.url == "mailto:test@example.com"
    assert isinstance(item.creation_time, datetime)
    assert isinstance(item.last_modified_time, datetime)

@pytest.mark.asyncio
async def test_get_items_hubspot_success(mock_httpx_client):
    # Mock credentials
    mock_credentials = json.dumps({
        "access_token": "test_token"
    })
    
    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{
            "id": "123",
            "properties": {
                "email": "test@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "createdate": "2024-01-01T12:00:00.000Z",
                "lastmodifieddate": "2024-01-01T12:00:00.000Z"
            }
        }]
    }
    mock_httpx_client.get.return_value = mock_response
    
    # Execute function
    result = await get_items_hubspot(mock_credentials)
    
    # Assertions
    assert len(result) == 1
    assert mock_httpx_client.get.call_args[1]['headers']['Authorization'] == "Bearer test_token"

@pytest.mark.asyncio
async def test_token_generation_success(mock_httpx_client):
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600
    }
    mock_httpx_client.post.return_value = mock_response
    
    # Execute function
    result = await tokenGeneration("test_code")
    
    # Assertions
    assert result["access_token"] == "test_token"
    assert result["expires_in"] == 3600
    assert mock_httpx_client.post.called

    # Verify the correct payload was sent
    call_args = mock_httpx_client.post.call_args
    assert call_args[1]['data']['grant_type'] == "authorization_code"
    assert call_args[1]['data']['code'] == "test_code"
    assert call_args[1]['data']['client_id'] == CLIENT_ID
    assert call_args[1]['data']['client_secret'] == CLIENT_SECRET
