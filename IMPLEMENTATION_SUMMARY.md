# SUMMARY: Figshare API 403 Error Resolution

## Problem Identified
Your GitHub Actions workflow was failing with a **403 Forbidden** error when trying to access the Figshare API `/articles/search` endpoint.

## Root Cause
The Figshare API requires authentication for the `/articles/search` POST endpoint. While your Python code already supported token authentication through the `FIGSHARE_TOKEN` environment variable, the GitHub Actions workflow was not passing this token to the script.

## Changes Made

### 1. Updated GitHub Actions Workflow
**File**: `.github/workflows/figshare-processing.yaml`

Added the `FIGSHARE_TOKEN` environment variable to the Python script execution step:
```yaml
- name: Run figshare exporter
  env:
    FIGSHARE_TOKEN: ${{ secrets.FIGSHARE_TOKEN }}
  run: |
    set -e
    cd ./output
    python ../figshare.py --force-refresh
```

### 2. Enhanced Error Handling
**File**: `figshare.py`

- Added logging on initialization to warn if no token is present
- Enhanced error handling in `__get()` and `__post()` methods to detect 403 errors
- Provides helpful error messages directing users to setup instructions

### 3. Comprehensive Documentation
Created two new documentation files:

**FIGSHARE_API_RESEARCH.md**
- Detailed analysis of 403 error causes
- Explanation of Figshare API authentication
- Step-by-step token setup instructions
- Additional recommendations for retry logic and error handling

**README.md**
- Complete project overview and setup guide
- How to obtain a Figshare API token
- Usage instructions and command-line arguments
- Troubleshooting section
- Output files explanation

## REQUIRED ACTION: Setup Figshare API Token

To resolve the 403 error, you **must** add a Figshare API token to your GitHub repository:

### Step 1: Obtain a Figshare API Token
1. Go to https://figshare.com and create an account (or log in)
2. Navigate to **Account Settings** → **Applications**
3. Click **"Create Personal Token"** or **"Create New Application"**
4. Name it (e.g., "LCAS eprint cache GitHub Actions")
5. Select **read permissions** for public articles
6. Generate and copy the token

### Step 2: Add Token to GitHub Secrets
1. Go to your repository: https://github.com/LCAS/eprint_cache
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. **Name**: `FIGSHARE_TOKEN`
5. **Value**: Paste the token from Figshare
6. Click **"Add secret"**

### Step 3: Test the Fix
Once you've added the secret:
1. The workflow will automatically use it on the next run
2. You can manually trigger a workflow run to test it immediately
3. Go to **Actions** tab → Select the workflow → Click **"Run workflow"**

## What Happens Now

✅ **With the token configured**:
- The workflow will authenticate with Figshare API
- Requests will succeed without 403 errors
- Higher rate limits will apply
- Reliable access to publication data

❌ **Without the token**:
- The code will still run but issue warnings
- Anonymous requests may fail with 403 errors
- Lower rate limits apply
- Workflow will likely fail

## Benefits of These Changes

1. **Clear Error Messages**: If the token is missing or invalid, you'll see helpful error messages
2. **Better Logging**: The script now logs whether it's using authenticated or anonymous requests
3. **Complete Documentation**: README provides full setup and usage instructions
4. **Research Documentation**: Detailed analysis of the issue for future reference

## Testing Locally

To test the changes locally:
```bash
export FIGSHARE_TOKEN="your_token_here"
python figshare.py --authors "Marc Hanheide" --debug
```

## Questions or Issues?

If you encounter any problems after setting up the token:
1. Check that the secret name is exactly `FIGSHARE_TOKEN`
2. Verify the token hasn't expired in Figshare
3. Review the workflow logs for specific error messages
4. See `FIGSHARE_API_RESEARCH.md` for detailed troubleshooting

---

**Next Step**: Please add the `FIGSHARE_TOKEN` secret to your repository as described above. This is the only remaining action needed to fully resolve the 403 error.
