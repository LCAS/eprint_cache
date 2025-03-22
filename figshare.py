#!/usr/bin/env python
# -*- coding: utf-8 -*-

from requests import get, post
from json import loads
from pprint import pformat
import pandas as pd
from functools import lru_cache, wraps
from datetime import datetime

from logging import getLogger, basicConfig, INFO, DEBUG
import os
from pickle import load, dump

from flatten_dict import flatten


import urllib.request

import requests
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase

import shelve
import re
import argparse
from datetime import datetime
from difflib import SequenceMatcher


basicConfig(level=INFO)
logger = getLogger(__name__)

class doi2bib:
    
    def __init__(self):
        self.bibtext_cache_file = "bibtext_cache"
        self.shortdoi_cache_file = "shortdoi_cache"
        self.logger = getLogger("doi2bib")
        self.logger.setLevel(INFO)


    def shorten(self, doi):
        """
        Get the shortDOI for a DOI. Providing a cache dictionary will prevent
        multiple API requests for the same DOI.
        """
        with shelve.open(self.shortdoi_cache_file) as cache:
            if doi in cache:
                self.logger.debug(f"short doi for {doi} found in cache")
                return cache[doi]
            quoted_doi = urllib.request.quote(doi)
            url = 'http://shortdoi.org/{}?format=json'.format(quoted_doi)
            try:
                response = requests.get(url).json()
                short_doi = response['ShortDOI']
            except Exception as e:
                self.logger.warning(f"failed to get short doi for {doi}: {e}")
                return None
            self.logger.debug(f"short doi for {doi} is {short_doi}, caching it")
            cache[doi] = short_doi
            return short_doi

    def get_bibtext(self, doi):
        """
        Use DOI Content Negotioation (http://crosscite.org/cn/) to retrieve a string
        with the bibtex entry.
        """
        with shelve.open(self.bibtext_cache_file) as cache:
            if doi in cache:
                self.logger.debug(f"bibtex for {doi} found in cache")
                return cache[doi]
            url = 'https://doi.org/' + urllib.request.quote(doi)
            header = {
                'Accept': 'application/x-bibtex',
            }
            response = requests.get(url, headers=header)
            bibtext = response.text
            if bibtext:
                self.logger.debug(f"bibtex for {doi} found, caching it")
                cache[doi] = bibtext
            else:
                self.logger.warning(f"failed to get bibtex for {doi}")
        return bibtext

    def get_bibtex_entry(self, doi):
        """
        Return a bibtexparser entry for a DOI
        """
        bibtext = self.get_bibtext(doi)
        if not bibtext:
            return None

        short_doi = self.shorten(doi)
        parser = BibTexParser()
        parser.ignore_nonstandard_types = False
        bibdb = bibtexparser.loads(bibtext, parser)
        entry, = bibdb.entries
        quoted_doi = urllib.request.quote(doi)
        entry['link'] = 'https://doi.org/{}'.format(quoted_doi)
        if 'author' in entry:
            entry['author'] = ' and '.join(entry['author'].rstrip(';').split('; '))
        entry['ID'] = short_doi[3:]
        return entry

    def entries_to_str(self, entries):
        """
        Pass a list of bibtexparser entries and return a bibtex formatted string.
        """
        db = BibDatabase()
        db.entries = entries
        return bibtexparser.dumps(db)


class FigShare:
    def __init__(self, page_size=100):
        self.logger = getLogger("FigShare")
        self.token = os.getenv('FIGSHARE_TOKEN')
        self.page_size = page_size
        self.base_url = "https://api.figshare.com/v2"

        # if cache file exist, load it
        self.cache_file = "figshare_cache.pkl"
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self.__cache = load(f)
                self.logger.debug(f"Loaded cache from {self.cache_file} with {len(self.__cache)} entries")
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")
                self.__cache = {}
        else:
            self.logger.info(f"No cache file found at {self.cache_file}")
            self.__cache = {}

    def save_cache(self):
        with open(self.cache_file,"wb") as f:
            dump(self.__cache, f)


    def __init_params(self):
        return {
            "page_size": self.page_size
        }

    def __get(self, url, params=None, use_cache=True):
        hash_key = f"GET{url}?{params}"
        if hash_key in self.__cache and use_cache:
            return self.__cache[hash_key]
        else:
            headers = { "Authorization": "token " + self.token } if self.token else {}
            result = get(self.base_url + url, headers=headers, params=params).json()
            self.__cache[hash_key] = result
            self.save_cache()
            return result

    def __post(self, url, params=None, use_cache=True):
        hash_key = f"POST{url}?{params}"
        if hash_key in self.__cache and use_cache:
            return self.__cache[hash_key]
        else:
            headers = { "Authorization": "token " + self.token } if self.token else {}
            result = post(self.base_url + url, headers=headers, params=params).json()
            self.__cache[hash_key] = result
            self.save_cache()
            return result

        
    def articles_by_user_name(self, user_name, use_cache=True):
        params = self.__init_params()
        params["search_for"] = f':author: \"{user_name}\"'
        page = 1
        articles = []
        while True:
            params["page"] = page
            self.logger.info(f"retrieving page {page} for user {user_name}")
            current_page_articles = self.__post("/articles/search", params=params, use_cache=use_cache)
            page += 1
            if len(current_page_articles) == 0:
                break
            articles += current_page_articles
        self.logger.info(f"found {len(articles)} articles for user {user_name}")

        return articles
    
    def get_article(self, article_id, use_cache=True):
        return self.__get(f"/articles/{article_id}", use_cache=use_cache)

class Author:
    def __init__(self, name, debug=False):
        self.logger = getLogger("Author")
        if debug:
            self.logger.setLevel(DEBUG)
        self.name = name
        self.fs = FigShare()
        self.articles = {}
        self.public_html_prefix = "https://repository.lincoln.ac.uk"
        self.df = None

    def save(self, filename=None):
        if filename is None:
            filename = f"{self.name}.db"
        with shelve.open(filename) as db:
            db['articles'] = self.articles
            db['df'] = self.df

    def load(self, filename=None):
        if filename is None:
            filename = f"{self.name}.db"
        with shelve.open(filename) as db:
            self.articles = db['articles']
            self.df = db['df']
    

    def _retrieve_figshare(self, use_cache=True):
        self.logger.info(f"retrieving articles for {self.name}")
        self.articles = self.fs.articles_by_user_name(self.name, use_cache=use_cache)

        self.logger.info(f"found {len(self.articles)} articles for {self.name}")

    def _retrieve_details(self, use_cache=True):
        for article in self.articles:
            self.logger.info(f"retrieving details for article {article['id']}")
            article['details'] = self.fs.get_article(article['id'], use_cache=use_cache)

    def _remove_non_repository(self):
        self.logger.info(f"removing non-repository articles out of {len(self.articles)}")
        self.articles = [a for a in self.articles if a['url_public_html'].startswith(self.public_html_prefix)]
        self.logger.info(f"retained {len(self.articles)} articles")

    def _custom_fields_to_dicts(self):
        for article in self.articles:
            if 'details' not in article:
                continue
            if 'custom_fields' not in article['details']:
                continue
            self.logger.debug(f"convert")

            cf = article['details']['custom_fields']
            if type(cf) == list:
                new_cf = {}
                for p in cf:
                    new_cf[p['name']] = p['value']
                article['details']['custom_fields'] = new_cf


    def _guess_doi(self, article):
        """
        Use crossref API to guess the DOI for an article based on the title and authors
        """
        with shelve.open("crossref_cache.db") as cache:
            if 'title' not in article or not article['title']:
                self.logger.warning("No title found for article, can't guess DOI")
                return None
            
            title = article['title']
            author = article['author']
            
            if title in cache:
                self.logger.info(f"Found DOI {cache[title]} in cache for title: {title}")
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
                
                self.logger.debug(f"Querying Crossref for title: {title}")
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data["message"]["total-results"] == 0:
                    self.logger.debug(f"No DOI found for: {title}")
                    return None
                
                # Get all matches and find the best one using fuzzy matching
                items = data["message"]["items"]
                if items:
                    self.logger.debug(f"Found {len(items)} potential matches for title: {title}")
                    
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
                        authors_last_name = article['author'].split()[-1]
                        
                        if doi and authors_last_name in authors_string:
                            self.logger.info(f"Found DOI {doi} for title: {title} (match score: {best_score:.2f})")
                            cache[title] = doi
                            return doi
                        else:
                            self.logger.warning(f"DOI found but author {authors_last_name} not in authors list or DOI missing")
                    else:
                        self.logger.warning(f"No good title match found. Best score was {best_score:.2f}, below threshold {threshold}")
                        self.logger.warning(f"  '{title}' != '{best_match['title'][0]}' (score: {best_score:.2f})")
                    
                    return None
            
            except Exception as e:
                self.logger.warning(f"Error guessing DOI: {e}")
            
            return None


    def _retrieve_bibtex_from_dois(self):
        if self.df is None:
            self.logger.warning(f"no dataframe found for {self.name}, can't continue")
            return
        doi2bibber = doi2bib()
        # iteratre over all rows in the dataframe self.df
        for index, row in self.df.iterrows():
            doi = row['External DOI']
            # Check if DOI is in valid format
            if doi and isinstance(doi, str):
                # Basic DOI validation - should start with 10. followed by numbers/dots/hyphens
                if not doi.startswith('10.') or not len(doi.split('/', 1)) == 2:
                    self.logger.warning(f"Invalid DOI format: {doi}, will try to guess")
                    doi = None
            else:
                self.logger.info(f"No DOI defined in record for article, will try to guess")
                doi = None
            if doi is None:
                doi = self._guess_doi(row)
                if doi is None:
                    self.logger.debug(f"Unable to guess DOI for article, no option left but to skip it")
                    continue
                self.logger.info(f"Guessed DOI for article: {doi}, updating dataframe")
                self.df.at[index, 'External DOI'] = doi
            try:
                bibtex = doi2bibber.get_bibtex_entry(doi)
                # Update the dataframe with the bibtex information
                if bibtex is not None:
                    self.df.at[index, 'bibtex'] = bibtex
                    self.df.at[index, 'bibtex_str'] = doi2bibber.entries_to_str([bibtex])
                    self.logger.info(f"got bibtex for {doi}")
                else:
                    self.logger.warning(f"Couldn't get bibtex for {doi}")

            except Exception as e:
                self.logger.warning(f"Failed to get bibtex for {doi}: {e}")
    
    def _flatten(self):
        new_articles = []
        for a in self.articles:
            new_articles.append(flatten(a, reducer='path'))
        self.articles = new_articles

    def retrieve(self, use_cache=True):
        self._retrieve_figshare(use_cache=use_cache)
        self._remove_non_repository()
        self._retrieve_details()
        self._custom_fields_to_dicts()
        self._flatten()
        self._create_dataframe()
        self._retrieve_bibtex_from_dois()

    def _create_dataframe(self):
        if len(self.articles) == 0:
            self.logger.warning(f"no articles found for {self.name}, can't create dataframe")
            self.df = None
            return
        self.df = pd.DataFrame.from_dict(self.articles)
        # add column with author name
        self.df['author'] = self.name
        # add column with online date (as datetime object)
        self.df['online_date'] = pd.to_datetime(self.df['timeline/firstOnline'], utc=True)
        # add column with online year
        self.df['online_year'] = self.df['online_date'].apply(
            lambda x: x.year
        )
        # add column with external DOI, parsed from custom_fields
        self.df['External DOI'] = self.df['details/custom_fields/External DOI'].apply(
            lambda x: re.sub(r'^(?:https?://doi\.org/|doi:)', '', x[0], flags=re.IGNORECASE).replace('doi:','')
            if isinstance(x, list) and len(x) > 0 else None
        )



        return self.df


def doi2bibtex_test():
    doi = "10.1109/MRA.2023.3296983"
    doi2bibber = doi2bib()
    bibtex = doi2bibber.get_bibtex_entry(doi)
    print(doi2bibber.entries_to_str([bibtex]))
    


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process publications from FigShare repository for specified authors.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-a', '--authors', nargs='+', 
                        help='List of author names to process')
    parser.add_argument('-f', '--authors-file', type=str,
                        help='Path to file containing list of authors (one per line)')
    parser.add_argument('-s', '--since', type=str, default='2021-01-01',
                        help='Process only publications since this date (YYYY-MM-DD)')
    parser.add_argument('-o', '--output', type=str, default='figshare_articles.csv',
                        help='Output CSV filename for publications, without duplicates')
    parser.add_argument('-O', '--output-all', type=str, default='figshare_articles_all.csv',
                        help='Output CSV filename for all publications by authors (includes duplicates when multiple authors per output)')
    # parser.add_argument('-r', '--recent-output', type=str, default='figshare_articles_recent.csv',
    #                     help='Output CSV filename for publications since specified date')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Force refresh data instead of loading from cache')
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

def figshare_processing():
    """
    Process FigShare publications for specified authors.
    
    This function:
    1. Retrieves publication data for each author from FigShare
    2. Combines all publications into a single dataset
    3. Removes duplicates while preserving author information
    4. Filters publications by date if specified
    5. Exports results to CSV files
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
    all_articles = []
    df_all = None
    
    for author_name in authors_list:
        logger.info(f"*** Processing {author_name}...")
        
        authors[author_name] = Author(author_name, debug=args.debug)
        cache_exists = os.path.exists(f"{author_name}.db")
        
        if cache_exists and not args.force_refresh:
            logger.info(f"Loading cached data for {author_name}")
            authors[author_name].load()
        else:
            logger.info(f"Retrieving data for {author_name}")
            authors[author_name].retrieve(not args.force_refresh)
            authors[author_name].save()
            
        if authors[author_name].df is not None:
            if df_all is None:
                df_all = authors[author_name].df
            else:
                df_all = pd.concat([df_all, authors[author_name].df])
            all_articles.extend(authors[author_name].articles)

            authors[author_name].df.to_csv(f"{author_name}.csv", index=False, encoding='utf-8')
            bibtex_filename = f"{author_name}.bib"
            bibtex = BibDatabase()
            bibtex.entries = [entry for entry in authors[author_name].df['bibtex'].tolist() if isinstance(entry, dict)]
            with open(bibtex_filename, 'w') as f:
                f.write(bibtexparser.dumps(bibtex))
            logger.info(f"Saved bibtex entries to {bibtex_filename}")

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

    # export bibtex file
    bibtex_filename = "lcas.bib"
    # with open(bibtex_filename, 'w') as f:
    #     for index, row in deduplicated_df.iterrows():
    #         if 'bibtex_str' in row and isinstance(row['bibtex_str'], str):
    #             f.write(row['bibtex_str'])
    #             f.write("\n\n")
    #     logger.info(f"Saved bibtex entries to {bibtex_filename}")
    bibtex = BibDatabase()
    bibtex.entries = [entry for entry in deduplicated_df['bibtex'].tolist() if isinstance(entry, dict)]
    with open(bibtex_filename, 'w') as f:
        f.write(bibtexparser.dumps(bibtex))
    logger.info(f"Saved bibtex entries to {bibtex_filename}")

    # Save all data to CSV
    deduplicated_df.to_csv(args.output, index=False, encoding='utf-8')
    logger.info(f"Saved deduplicated articles to {args.output}")

    # Save all data to CSV
    df_all.to_csv(args.output_all, index=False, encoding='utf-8')
    logger.info(f"Saved all articles to {args.output_all}")

    # # Parse the since date
    # try:
    #     since_date = pd.Timestamp(datetime.strptime(args.since, '%Y-%m-%d')).tz_localize('UTC')
    #     filtered_df = deduplicated_df[deduplicated_df['online_date'] > since_date]
    #     filtered_df.to_csv(args.recent_output, index=False, encoding='utf-8')
    #     logger.info(f"Saved {len(filtered_df)} articles since {args.since} to {args.recent_output}")
    # except ValueError as e:
    #     logger.error(f"Invalid date format: {e}. Expected YYYY-MM-DD.")

    logger.info("Processing complete")

if __name__ == "__main__":
    figshare_processing()
