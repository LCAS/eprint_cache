#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script 2: Read CSV files and generate bibtex from article details

This script:
1. Reads the deduplicated CSV file produced by figshare_fetch.py
2. Retrieves article details and DOIs
3. Generates bibtex entries for each article
4. Exports bibtex files
"""

import pandas as pd
import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
import argparse
import re
import requests
import shelve
from logging import getLogger, basicConfig, INFO, DEBUG
from difflib import SequenceMatcher

from doi2bib import doi2bib

basicConfig(level=INFO)
logger = getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Read CSV file and generate bibtex entries from article details.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-i', '--input', type=str, default='figshare_articles.csv',
                        help='Input CSV filename (deduplicated articles from figshare_fetch.py)')
    parser.add_argument('-o', '--output', type=str, default='lcas.bib',
                        help='Output bibtex filename')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    
    return parser.parse_args()


def guess_doi(article_row):
    """
    Use crossref API to guess the DOI for an article based on the title and authors
    """
    with shelve.open("crossref_cache.db") as cache:
        if 'title' not in article_row or not article_row['title']:
            logger.warning("No title found for article, can't guess DOI")
            return None
        
        title = article_row['title']
        author = article_row['author']
        
        if title in cache:
            logger.info(f"Found DOI {cache[title]} in cache for title: {title}")
            return cache[title]

        # Construct query URL for Crossref API
        base_url = "https://api.crossref.org/works"
        params = {
            "query.query.bibliographic": f"{title}",
            "query.author": f"{author}",
            "sort": "relevance",
            "rows": 10,  # Get top 10 matches
            "select": "DOI,title,author",
        }
        
        try:
            
            logger.debug(f"Querying Crossref for title: {title}")
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            
            # Check if response is valid and contains JSON
            if response.ok and response.headers.get('Content-Type', '').lower().startswith('application/json') and response.text.strip():
                data = response.json()
            else:
                logger.warning(f"Received empty or invalid JSON response from Crossref API (status: {response.status_code})")
                return None
            
            if data["message"]["total-results"] == 0:
                logger.debug(f"No DOI found for: {title}")
                return None
            
            # Get all matches and find the best one using fuzzy matching
            items = data["message"]["items"]
            if items:
                logger.debug(f"Found {len(items)} potential matches for title: {title}")
                
                best_match = None
                best_score = 0
                threshold = 0.8  # Minimum similarity score to accept a match
                
                for item in items:
                    if "title" in item and item["title"]:
                        item_title = item["title"][0]
                        # Calculate similarity score
                        score = SequenceMatcher(None, title.lower(), item_title.lower()).ratio()
                        logger.debug(f"==== '{title}' == '{item['title'][0]}'??? ==> {score:.2f}")
                        
                        if score > best_score:
                            best_score = score
                            best_match = item
                
                if best_match and best_score >= threshold:
                    doi = best_match.get("DOI")
                    authors_string = str(best_match.get("author", ""))
                    authors_last_name = author.split()[-1]
                    
                    if doi and authors_last_name in authors_string:
                        logger.info(f"Found DOI {doi} for title: {title} (match score: {best_score:.2f})")
                        cache[title] = doi
                        return doi
                    else:
                        logger.warning(f"DOI found but author {authors_last_name} not in authors list or DOI missing")
                else:
                    logger.warning(f"No good title match found. Best score was {best_score:.2f}, below threshold {threshold}")
                    if best_match:
                        logger.warning(f"  '{title}' != '{best_match['title'][0]}' (score: {best_score:.2f})")
                
                return None
        
        except Exception as e:
            logger.warning(f"Error guessing DOI: {e}")
        
        return None


def retrieve_bibtex_from_dois(df):
    """
    Retrieve bibtex entries for all articles in the dataframe
    """
    if df is None or len(df) == 0:
        logger.warning(f"no dataframe provided, can't continue")
        return df
    
    doi2bibber = doi2bib()
    
    # Add bibtex columns if they don't exist
    if 'bibtex' not in df.columns:
        df['bibtex'] = None
    if 'bibtex_str' not in df.columns:
        df['bibtex_str'] = None
    
    # Iterate over all rows in the dataframe
    for index, row in df.iterrows():
        doi = row['External DOI'] if 'External DOI' in row else None
        
        # Check if DOI is in valid format
        if doi and isinstance(doi, str):
            # Basic DOI validation - should start with 10. followed by numbers/dots/hyphens
            if not doi.startswith('10.') or not len(doi.split('/', 1)) == 2:
                logger.warning(f"Invalid DOI format: {doi}, will try to guess")
                doi = None
        else:
            logger.info(f"No DOI defined in record for article, will try to guess")
            doi = None
        
        if doi is None:
            doi = guess_doi(row)
            if doi is None:
                logger.debug(f"Unable to guess DOI for article, no option left but to skip it")
                continue
            logger.info(f"Guessed DOI for article: {doi}, updating dataframe")
            df.at[index, 'External DOI'] = doi
        
        try:
            bibtex = doi2bibber.get_bibtex_entry(doi)
            # Update the dataframe with the bibtex information
            if bibtex is not None:
                df.at[index, 'bibtex'] = bibtex
                df.at[index, 'bibtex_str'] = doi2bibber.entries_to_str([bibtex])
                logger.info(f"got bibtex for {doi}")
            else:
                logger.warning(f"Couldn't get bibtex for {doi}")

        except Exception as e:
            logger.warning(f"Failed to get bibtex for {doi}: {e}")
    
    return df


def figshare_bibtex():
    """
    Read CSV file and generate bibtex entries from article details.
    
    This function:
    1. Reads the deduplicated CSV file
    2. Retrieves bibtex for each article based on DOI
    3. Exports bibtex file
    """
    args = parse_args()
    
    if args.debug:
        logger.setLevel(DEBUG)
    
    # Check if input file exists
    import os
    if not os.path.exists(args.input):
        logger.error(f"Input file {args.input} not found. Please run figshare_fetch.py first.")
        return
    
    logger.info(f"Reading articles from {args.input}")
    df = pd.read_csv(args.input, encoding='utf-8')
    logger.info(f"Loaded {len(df)} articles from CSV")
    
    # Retrieve bibtex for all articles
    logger.info("Retrieving bibtex entries for all articles...")
    df = retrieve_bibtex_from_dois(df)
    
    # Export bibtex file
    bibtex_filename = args.output
    bibtex = BibDatabase()
    bibtex.entries = [entry for entry in df['bibtex'].tolist() if isinstance(entry, dict)]
    
    # Process all entries in the bibtex database and remove any duplicates based on ID
    unique_entries = {}
    for entry in bibtex.entries:
        if entry and 'ID' in entry:
            # Use ID as the key to avoid duplicates
            unique_entries[entry['ID']] = entry
        else:
            logger.debug(f"Skipping entry without ID: {entry}")

    logger.info(f"Reduced from {len(bibtex.entries)} to {len(unique_entries)} unique bibtex entries")
    
    # Replace the entries with the unique ones
    bibtex.entries = list(unique_entries.values())
    
    with open(bibtex_filename, 'w') as f:
        f.write(bibtexparser.dumps(bibtex))
    
    logger.info(f"Saved {len(unique_entries)} bibtex entries to {bibtex_filename}")
    logger.info("Bibtex generation complete")


if __name__ == "__main__":
    figshare_bibtex()
