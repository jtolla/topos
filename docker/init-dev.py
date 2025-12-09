#!/usr/bin/env python3
"""
Initialize the Strata development environment.

This script:
1. Waits for the API to be ready
2. Creates a dev tenant with an API key
3. Creates an estate and share for the dev agent
4. Outputs the API key for use by the agent
"""

import os
import sys
import time
import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")
MAX_RETRIES = 30
RETRY_DELAY = 2


def wait_for_api():
    """Wait for the API to be ready."""
    print(f"Waiting for API at {API_BASE_URL}...")

    for i in range(MAX_RETRIES):
        try:
            response = httpx.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("API is ready!")
                return True
        except Exception as e:
            pass

        print(f"  Attempt {i + 1}/{MAX_RETRIES}...")
        time.sleep(RETRY_DELAY)

    print("ERROR: API did not become ready in time")
    return False


def create_tenant(client: httpx.Client) -> dict:
    """Create a development tenant."""
    print("Creating dev tenant...")

    response = client.post(
        f"{API_BASE_URL}/api/tenants",
        json={
            "name": "dev-tenant",
            "config": {
                "embeddings_enabled": False,
                "classification_enabled": True,
            }
        }
    )

    if response.status_code == 409:
        # Tenant already exists, fetch it
        print("  Tenant already exists, fetching...")
        response = client.get(f"{API_BASE_URL}/api/tenants")
        tenants = response.json()
        for tenant in tenants:
            if tenant["name"] == "dev-tenant":
                return tenant
        raise Exception("Could not find dev-tenant")

    response.raise_for_status()
    tenant = response.json()
    print(f"  Created tenant: {tenant['id']}")
    return tenant


def create_api_key(client: httpx.Client, tenant_id: str) -> str:
    """Create an API key for the tenant."""
    print("Creating API key...")

    response = client.post(
        f"{API_BASE_URL}/api/tenants/{tenant_id}/api-keys",
        json={
            "name": "dev-agent-key",
            "scopes": ["read", "write", "ingest"]
        }
    )

    if response.status_code == 409:
        print("  API key already exists")
        # Return a placeholder - in real scenario we'd need to handle this
        return "existing-key"

    response.raise_for_status()
    key_data = response.json()
    api_key = key_data.get("key") or key_data.get("api_key")
    print(f"  Created API key: {api_key[:8]}...")
    return api_key


def create_estate(client: httpx.Client, tenant_id: str, api_key: str) -> dict:
    """Create an estate for file organization."""
    print("Creating estate...")

    headers = {"X-API-Key": api_key}

    response = client.post(
        f"{API_BASE_URL}/api/estates",
        headers=headers,
        json={
            "name": "dev-estate",
            "description": "Development estate for testing"
        }
    )

    if response.status_code == 409:
        print("  Estate already exists, fetching...")
        response = client.get(f"{API_BASE_URL}/api/estates", headers=headers)
        estates = response.json()
        for estate in estates:
            if estate["name"] == "dev-estate":
                return estate
        raise Exception("Could not find dev-estate")

    response.raise_for_status()
    estate = response.json()
    print(f"  Created estate: {estate['id']}")
    return estate


def create_share(client: httpx.Client, estate_id: str, api_key: str) -> dict:
    """Create a share for the SMB mount."""
    print("Creating share...")

    headers = {"X-API-Key": api_key}

    response = client.post(
        f"{API_BASE_URL}/api/estates/{estate_id}/shares",
        headers=headers,
        json={
            "name": "documents",
            "source_uri": "smb://samba/documents",
            "mount_point": "/mnt/documents"
        }
    )

    if response.status_code == 409:
        print("  Share already exists")
        return {"name": "documents", "status": "existing"}

    response.raise_for_status()
    share = response.json()
    print(f"  Created share: {share.get('id', 'documents')}")
    return share


def main():
    """Main initialization routine."""
    print("=" * 60)
    print("Strata Development Environment Initialization")
    print("=" * 60)
    print()

    # Wait for API
    if not wait_for_api():
        sys.exit(1)

    print()

    with httpx.Client(timeout=30) as client:
        # Create tenant
        tenant = create_tenant(client)
        tenant_id = tenant["id"]

        # Create API key
        api_key = create_api_key(client, tenant_id)

        # Create estate
        estate = create_estate(client, tenant_id, api_key)
        estate_id = estate["id"]

        # Create share
        share = create_share(client, estate_id, api_key)

    print()
    print("=" * 60)
    print("Initialization Complete!")
    print("=" * 60)
    print()
    print("API Key for agent:")
    print(f"  {api_key}")
    print()
    print("Set this in your environment or agent config:")
    print(f"  export STRATA_API_KEY={api_key}")
    print()

    # Write API key to a file for the agent to read
    key_file = "/config/api-key"
    try:
        with open(key_file, "w") as f:
            f.write(api_key)
        print(f"API key written to {key_file}")
    except Exception as e:
        print(f"Could not write API key to file: {e}")


if __name__ == "__main__":
    main()
