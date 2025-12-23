# LCAS EPrint Cache

This repository automatically exports and caches publication data from Figshare for LCAS (Lincoln Centre for Autonomous Systems) researchers.

## Overview

The system:
- Retrieves publication metadata from Figshare repository
- Processes author information and generates BibTeX entries
- Exports data in CSV and BibTeX formats
- Publishes to Nexus repository for public access

## Setup

### Prerequisites

- Python 3.10+
- Figshare API token (required)

### Configuration

#### Figshare API Token

This application requires a Figshare API token to function properly. To set up:

1. **Create a Figshare account**: Visit [https://figshare.com](https://figshare.com) and create an account
2. **Generate an API token**:
   - Log in to Figshare
   - Go to Account Settings → Applications
   - Create a new personal token
   - Copy the token securely
3. **For local development**: Set the environment variable
   ```bash
   export FIGSHARE_TOKEN="your_token_here"
   ```
4. **For GitHub Actions**: Add the token as a repository secret named `FIGSHARE_TOKEN`
   - Go to repository Settings → Secrets and variables → Actions
   - Create a new secret named `FIGSHARE_TOKEN`
   - Paste your Figshare API token

**Note**: Without a valid API token, requests to the Figshare API will fail with 403 errors.

### Installation

```bash
# Install dependencies
pip install -r requirements-frozen.txt
```

## Usage

### Command Line

```bash
# Run with default authors list
python figshare.py

# Run with specific authors
python figshare.py --authors "Marc Hanheide" "Tom Duckett"

# Run with authors from file
python figshare.py --authors-file staff.json

# Force refresh (ignore cache)
python figshare.py --force-refresh

# Enable debug logging
python figshare.py --debug

# Custom output filenames
python figshare.py --output my_articles.csv --output-all my_articles_all.csv
```

### Arguments

- `-a, --authors`: List of author names to process
- `-f, --authors-file`: Path to file containing author names (one per line)
- `-s, --since`: Process only publications since this date (YYYY-MM-DD), default: 2021-01-01
- `-o, --output`: Output CSV filename for deduplicated publications, default: figshare_articles.csv
- `-O, --output-all`: Output CSV filename for all publications (with duplicates), default: figshare_articles_all.csv
- `--force-refresh`: Force refresh data instead of loading from cache
- `--debug`: Enable debug logging

## Output Files

The script generates several output files:

- `lcas.bib`: Combined BibTeX file with all publications (deduplicated)
- `figshare_articles.csv`: CSV with deduplicated articles
- `figshare_articles_all.csv`: CSV with all articles (includes duplicates when multiple authors)
- `{author_name}.bib`: Individual BibTeX files per author
- `{author_name}.csv`: Individual CSV files per author
- `{author_name}.db`: Cached data per author (shelve database)

## Cache Files

The application uses several cache files to minimize API calls:

- `figshare_cache.pkl`: Cached Figshare API responses
- `bibtext_cache`: Cached BibTeX entries from DOI lookups
- `shortdoi_cache`: Cached short DOI mappings
- `crossref_cache.db`: Cached Crossref API responses for DOI guessing

## GitHub Actions Workflow

The workflow runs automatically:
- Weekly on Tuesdays at 02:30 UTC
- On push to main branch
- On pull requests
- Can be manually triggered via workflow_dispatch

### Workflow Steps

1. Checkout repository
2. Restore cache
3. Install Python dependencies
4. Run Figshare exporter
5. Publish results to Nexus repository
6. Upload artifacts

## Troubleshooting

### 403 Forbidden Errors

If you encounter 403 errors when accessing the Figshare API:
1. Ensure the `FIGSHARE_TOKEN` environment variable is set
2. Verify the token is valid and hasn't expired
3. Check that the token has appropriate permissions (read access to public articles)

For detailed information about the 403 error and resolution steps, see [FIGSHARE_API_RESEARCH.md](FIGSHARE_API_RESEARCH.md).

### Empty Results

If no articles are found:
- Check that author names match exactly as they appear in Figshare
- Verify the articles are in the Lincoln repository (https://repository.lincoln.ac.uk)
- Use `--debug` flag for detailed logging

### JSON Decode Errors

The application includes validation for JSON responses. If issues persist:
- Check your internet connection
- Verify Figshare API is accessible
- Review logs for specific error messages

## Development

### Running Tests

```bash
# Run with a single test author
python figshare.py --authors "Marc Hanheide" --debug
```

### Code Structure

- `figshare.py`: Main script with FigShare API client and processing logic
- `doi2bib`: Class for DOI to BibTeX conversion
- `FigShare`: Class for Figshare API interactions
- `Author`: Class for author-specific processing

## License

[Add license information here]

## Contact

For issues or questions, please open an issue in the GitHub repository.
