#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script 1: Fetch articles from Figshare API and create CSV files

This script:
1. Retrieves publication data for each author from FigShare API
2. Processes and flattens the article data
3. Creates deduplicated CSV files
4. Does NOT retrieve bibtex (handled by script 2)
"""

import pandas as pd
import os
import argparse
from logging import getLogger, basicConfig, INFO, DEBUG

from author import Author

basicConfig(level=INFO)
logger = getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch publications from FigShare repository for specified authors and create CSV files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-a', '--authors', nargs='+', 
                        help='List of author names to process (uses default list if not specified)')
    parser.add_argument('-f', '--authors-file', type=str,
                        help='Path to file containing list of authors, one per line (uses default list if not specified)')
    parser.add_argument('-o', '--output', type=str, default='figshare_articles.csv',
                        help='Output CSV filename for publications, without duplicates')
    parser.add_argument('-O', '--output-all', type=str, default='figshare_articles_all.csv',
                        help='Output CSV filename for all publications by authors (includes duplicates when multiple authors per output)')
    parser.add_argument('--use-author-cache', action='store_true',
                        help='Use cached author data instead of refreshing from API')
    parser.add_argument('--rate-limit-delay', type=float, default=1.0,
                        help='Delay in seconds between Figshare API requests (default: 1.0)')
    parser.add_argument('--max-retries', type=int, default=1,
                        help='Maximum number of retry attempts for 403 errors (default: 1)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    
    return parser.parse_args()


def load_authors_from_file(filename):
    """Load author names from a file, one per line."""
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Error loading authors from file {filename}: {e}")
        return []


def figshare_fetch():
    """
    Fetch FigShare publications for specified authors and create CSV files.
    
    This function:
    1. Retrieves publication data for each author from FigShare
    2. Combines all publications into a single dataset
    3. Removes duplicates while preserving author information
    4. Exports results to CSV files (without bibtex generation)
    """
    args = parse_args()
    
    if args.debug:
        logger.setLevel(DEBUG)
    
    # Get list of authors
    authors_list = []
    if args.authors:
        authors_list.extend(args.authors)
    if args.authors_file:
        authors_list.extend(load_authors_from_file(args.authors_file))
    
    # Use default authors if none specified
    if not authors_list:
        authors_list = [
            "Marc Hanheide", "Marcello Calisti", "Grzegorz Cielniak", 
            "Simon Parsons", "Elizabeth Sklar", "Paul Baxter", 
            "Petra Bosilj", "Heriberto Cuayahuitl", "Gautham Das", 
            "Francesco Del Duchetto", "Charles Fox", "Leonardo Guevara",
            "Helen Harman", "Mohammed Al-Khafajiy", "Alexandr Klimchik", 
            "Riccardo Polvara", "Athanasios Polydoros", "Zied Tayeb", 
            "Sepehr Maleki", "Junfeng Gao", "Tom Duckett", "Mini Rai", 
            "Amir Ghalamzan Esfahani"
        ]
        logger.info(f"Using default list of {len(authors_list)} authors")
    else:
        logger.info(f"Processing {len(authors_list)} authors from command line/file")

    authors = {}
    df_all = None
    
    for author_name in authors_list:
        logger.info(f"*** Processing {author_name}...")
        
        authors[author_name] = Author(author_name, debug=args.debug, rate_limit_delay=args.rate_limit_delay, max_retries=args.max_retries)
        cache_exists = os.path.exists(f"{author_name}.db")
        
        if cache_exists and args.use_author_cache:
            logger.info(f"Loading cached data for {author_name}")
            authors[author_name].load()
        else:
            logger.info(f"Retrieving data for {author_name}")
            # Call retrieve WITHOUT bibtex generation
            authors[author_name]._retrieve_figshare(use_cache=args.use_author_cache)
            authors[author_name]._remove_non_repository()
            authors[author_name]._retrieve_details(use_cache=True)
            authors[author_name]._custom_fields_to_dicts()
            authors[author_name]._flatten()
            authors[author_name]._create_dataframe()
            # Note: NOT calling _retrieve_bibtex_from_dois() here - that's for script 2
            authors[author_name].save()
            
        if authors[author_name].df is not None:
            if df_all is None:
                df_all = authors[author_name].df
            else:
                df_all = pd.concat([df_all, authors[author_name].df])

            # Save individual author CSV
            authors[author_name].df.to_csv(f"{author_name}.csv", index=False, encoding='utf-8')
            logger.info(f"Saved {len(authors[author_name].df)} articles for {author_name} to {author_name}.csv")
        else:
            logger.warning(f"No data found for {author_name}")

    if df_all is None or len(df_all) == 0:
        logger.error("No publication data found. Exiting.")
        return

    logger.info(f"Total number of articles before deduplication: {len(df_all)}")

    # Group by ID and aggregate authors into lists
    grouped = df_all.groupby('id').agg({
        'author': lambda x: list(set(x))  # Use set to remove duplicate authors
    })

    # Filter the original dataframe to keep only one row per ID
    deduplicated_df = df_all.drop_duplicates(subset=['id'], keep='first')

    # Add the aggregated authors list as a new column
    deduplicated_df = deduplicated_df.set_index('id')
    deduplicated_df['authors'] = grouped['author']
    deduplicated_df = deduplicated_df.reset_index()

    # Convert authors list to comma-separated string
    deduplicated_df['authors'] = deduplicated_df['authors'].apply(lambda authors: ', '.join(authors))

    logger.info(f"Total number of articles after deduplication: {len(deduplicated_df)}")

    # Save deduplicated data to CSV
    deduplicated_df.to_csv(args.output, index=False, encoding='utf-8')
    logger.info(f"Saved deduplicated articles to {args.output}")

    # Save all data to CSV
    df_all.to_csv(args.output_all, index=False, encoding='utf-8')
    logger.info(f"Saved all articles to {args.output_all}")

    logger.info("Fetch processing complete - CSV files created successfully")
    logger.info(f"Next step: Run figshare_bibtex.py to generate bibtex from {args.output}")


if __name__ == "__main__":
    figshare_fetch()
