# Figshare API 403 Error Research

## Issue Description
The workflow is experiencing 403 (Forbidden) errors when calling the Figshare API `/articles/search` endpoint.

## API Endpoint Information

### Endpoint: POST /v2/articles/search
- **Base URL**: https://api.figshare.com/v2
- **Method**: POST
- **Purpose**: Search for articles in Figshare repository

## Common Causes of 403 Errors in REST APIs

### 1. Authentication Required
Many public APIs require authentication even for read operations to:
- Prevent abuse and rate limiting
- Track usage
- Control access to certain features

### 2. Rate Limiting
APIs may return 403 when:
- Too many requests from the same IP
- Exceeding the allowed request rate
- No authentication token provided (forcing lower rate limits for anonymous users)

### 3. Geographic Restrictions
Some APIs block requests from certain regions or IP ranges

### 4. User-Agent Blocking
APIs may block requests that don't include proper User-Agent headers

## Figshare API Authentication

### Public vs Private Endpoints
Figshare API has two types of endpoints:
- **Public endpoints**: Generally don't require authentication (GET requests for public data)
- **Private endpoints**: Require authentication

### Authentication Methods
Figshare API supports OAuth2 authentication:
- Uses personal access tokens
- Token should be included in the Authorization header: `Authorization: token YOUR_TOKEN`

### POST /articles/search Endpoint
This endpoint performs a search operation using POST method (to allow complex search queries in the body).

**Key Issue**: While some Figshare search operations may work without authentication, the POST method to `/articles/search` may require authentication or have different rate limits compared to anonymous access.

## Current Implementation Analysis

Looking at `figshare.py` lines 125-176:

```python
def __init__(self, page_size=100):
    self.token = os.getenv('FIGSHARE_TOKEN')
    # ... token is optional
    
def __post(self, url, params=None, use_cache=True):
    headers = { "Authorization": "token " + self.token } if self.token else {}
    response = post(self.base_url + url, headers=headers, json=params)
```

**Current behavior**:
- Token is optional (read from environment variable)
- If no token is provided, requests are made anonymously
- This may work sometimes but fail with 403 when:
  - Rate limits are hit
  - API policy changes
  - IP-based restrictions apply

## Recommendations

### 1. Obtain a Figshare API Token

**How to get a token**:
1. Create a Figshare account at https://figshare.com
2. Go to Account Settings
3. Navigate to "Applications" or "API" section
4. Create a new application/token
5. Generate a personal access token
6. Copy and store the token securely

**Token Permissions**:
- For read-only operations (searching, retrieving articles), read permissions are sufficient
- No write permissions needed for this use case

### 2. Add Token to GitHub Secrets

**Steps**:
1. Go to repository Settings
2. Navigate to Secrets and variables → Actions
3. Create a new repository secret named `FIGSHARE_TOKEN`
4. Paste the Figshare API token
5. The workflow already references this secret in the environment (if added)

**Note**: Check if workflow file needs to be updated to pass the secret as an environment variable.

### 3. Update Workflow (if needed)

If not already present, add to `.github/workflows/figshare-processing.yaml`:

```yaml
env:
  FIGSHARE_TOKEN: ${{ secrets.FIGSHARE_TOKEN }}
```

Or in the specific job/step that runs the Python script.

## Alternative Solutions

### 1. Add Retry Logic with Exponential Backoff
If 403 is intermittent, add retry logic to handle temporary rate limit issues.

### 2. Add User-Agent Header
Some APIs require a proper User-Agent header. Update the request headers to include:
```python
headers = {
    "Authorization": f"token {self.token}" if self.token else "",
    "User-Agent": "LCAS-eprint-cache/1.0"
}
```

### 3. Implement Caching More Aggressively
The code already has caching, but ensure it's used effectively to minimize API calls.

### 4. Use GET endpoint if available
Check if there's a GET version of the articles/search endpoint that might have different authentication requirements.

## Workflow Configuration Issue

**Current Status**: The workflow file does NOT pass the `FIGSHARE_TOKEN` environment variable to the Python script.

Looking at `.github/workflows/figshare-processing.yaml`:
- Line 48-52: The "Run figshare exporter" step does not include any environment variables
- The Python script expects `FIGSHARE_TOKEN` via `os.getenv('FIGSHARE_TOKEN')` (figshare.py line 125)
- Without the token, all requests are anonymous and more likely to hit rate limits or be rejected

## Conclusion

**Root Cause**: The 403 error is caused by missing authentication when calling the Figshare API `/articles/search` endpoint.

**Evidence**:
1. The Python code supports token authentication (line 125, 158, 175)
2. The workflow file does not pass the `FIGSHARE_TOKEN` environment variable
3. Anonymous requests to POST endpoints are more restricted and likely to fail with 403

**Recommended Solution**:

### Step 1: Obtain a Figshare API Token
1. Create a Figshare account at https://figshare.com
2. Log in to your account
3. Go to Account Settings (click your profile icon → Settings)
4. Navigate to "Applications" section
5. Click "Create Personal Token" or "Create New Application"
6. Give it a descriptive name (e.g., "LCAS eprint cache GitHub Actions")
7. Select appropriate permissions (read access to public articles is sufficient)
8. Generate the token and copy it securely

### Step 2: Add Token to GitHub Repository Secrets
1. Go to the GitHub repository: https://github.com/LCAS/eprint_cache
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `FIGSHARE_TOKEN`
5. Value: Paste the Figshare API token
6. Click "Add secret"

### Step 3: Update Workflow to Pass Token
Add the environment variable to the "Run figshare exporter" step in `.github/workflows/figshare-processing.yaml`:

```yaml
- name: Run figshare exporter
  env:
    FIGSHARE_TOKEN: ${{ secrets.FIGSHARE_TOKEN }}
  run: |
    set -e
    cd ./output
    python ../figshare.py --force-refresh
```

### Step 4: Test the Changes
1. Create a pull request with the workflow change
2. The workflow should run automatically
3. Verify that the 403 error no longer occurs
4. Check that articles are successfully retrieved

## Additional Recommendations

### 1. Add Better Error Handling
Update the `__post` method to provide more informative error messages:

```python
def __post(self, url, params=None, use_cache=True):
    hash_key = f"POST{url}?{params}"
    if hash_key in self.__cache and use_cache:
        return self.__cache[hash_key]
    else:
        headers = { "Authorization": "token " + self.token } if self.token else {}
        response = post(self.base_url + url, headers=headers, json=params)
        
        if response.status_code == 403:
            self.logger.error(f"403 Forbidden: Authentication may be required. "
                            f"Ensure FIGSHARE_TOKEN environment variable is set. "
                            f"Response: {response.text}")
            return []
        
        if response.ok and response.headers.get('Content-Type', '').lower().startswith('application/json') and response.text.strip():
            result = response.json()
            self.__cache[hash_key] = result
            self.save_cache()
            return result
        else:
            self.logger.warning(f"Received empty or invalid JSON response for POST {self.base_url + url} (status: {response.status_code})")
            return []
```

### 2. Add Retry Logic
Consider adding retry logic with exponential backoff for transient errors:

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def __init__(self, page_size=100):
    self.logger = getLogger("FigShare")
    self.token = os.getenv('FIGSHARE_TOKEN')
    self.page_size = page_size
    self.base_url = "https://api.figshare.com/v2"
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    self.session = requests.Session()
    self.session.mount("https://", adapter)
```

### 3. Log Token Status
Add logging to indicate whether token authentication is being used:

```python
def __init__(self, page_size=100):
    self.logger = getLogger("FigShare")
    self.token = os.getenv('FIGSHARE_TOKEN')
    if self.token:
        self.logger.info("Using authenticated requests with FIGSHARE_TOKEN")
    else:
        self.logger.warning("No FIGSHARE_TOKEN found - using anonymous requests (may hit rate limits)")
    # ... rest of init
```

## References
- Figshare API Documentation: https://docs.figshare.com/
- Figshare API Reference: https://docs.figshare.com/#figshare-documentation-api-description
- Figshare API Authentication: https://docs.figshare.com/#authentication
- GitHub Actions Secrets: https://docs.github.com/en/actions/security-guides/encrypted-secrets
