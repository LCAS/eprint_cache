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
                self.logger.info(f"Loaded cache from {self.cache_file} with {len(self.__cache)} entries")
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

        
    def articles_by_user_name(self, user_name):
        params = self.__init_params()
        params["search_for"] = f':author: \"{user_name}\"'
        page = 1
        articles = []
        while True:
            params["page"] = page
            self.logger.info(f"retrieving page {page} for user {user_name}")
            current_page_articles = self.__post("/articles/search", params=params)
            page += 1
            if len(current_page_articles) == 0:
                break
            articles += current_page_articles
        self.logger.info(f"found {len(articles)} articles for user {user_name}")

        return articles
    
    def get_article(self, article_id):
        return self.__get(f"/articles/{article_id}")

class Author:
    def __init__(self, name):
        self.logger = getLogger("Author")
        self.name = name
        self.fs = FigShare()
        self.articles = {}
        self.public_html_prefix = "https://repository.lincoln.ac.uk"
        self.df = None

    def _retrieve_figshare(self):
        self.logger.info(f"retrieving articles for {self.name}")
        self.articles = self.fs.articles_by_user_name(self.name)

        self.logger.info(f"found {len(self.articles)} articles for {self.name}")

    def _retrieve_details(self):
        for article in self.articles:
            self.logger.info(f"retrieving details for article {article['id']}")
            article['details'] = self.fs.get_article(article['id'])

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

    def _retrieve_bibtex_from_dois(self):
        doi2bibber = doi2bib()
        # iteratre over all rows in the dataframe self.df
        for index, row in self.df.iterrows():
            doi = row['External DOI']
            # Check if DOI is in valid format
            if doi and isinstance(doi, str):
                # Basic DOI validation - should start with 10. followed by numbers/dots/hyphens
                if not doi.startswith('10.') or not len(doi.split('/', 1)) == 2:
                    self.logger.warning(f"Invalid DOI format: {doi}, skipping")
                    continue
            else:
                self.logger.debug(f"No DOI found for article, skipping")
                continue
            try:
                bibtex = doi2bibber.get_bibtex_entry(doi)
                row['bibtex'] = bibtex
                row['bibtex_str'] = doi2bibber.entries_to_str([bibtex])
                self.logger.info(f"got bibtex for {doi}")

            except Exception as e:
                self.logger.warning(f"Failed to get bibtex for {doi}: {e}")
    
    def _flatten(self):
        new_articles = []
        for a in self.articles:
            new_articles.append(flatten(a, reducer='path'))
        self.articles = new_articles

    def retrieve(self):
        self._retrieve_figshare()
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
            lambda x: re.sub(r'^(?:https?://doi\.org/|doi:)', '', x[0], flags=re.IGNORECASE)
            if isinstance(x, list) and len(x) > 0 else None
        )



        return self.df


def doi2bibtex_test():
    doi = "10.1109/MRA.2023.3296983"
    doi2bibber = doi2bib()
    bibtex = doi2bibber.get_bibtex_entry(doi)
    print(doi2bibber.entries_to_str([bibtex]))
    


def figshare_processing():
    authors = {}

    lcas_authors = [
        "Marc Hanheide",
        "Marcello Calisti",
        "Grzegorz Cielniak",
        "Simon Parsons",
        "Elizabeth Sklar",
        "Paul Baxter",
        "Petra Bosilj",
        "Heriberto Cuayahuitl",
        "Gautham Das",
        "Francesco Del Duchetto",
        "Charles Fox",
        "Leonardo Guevara",
        "Helen Harman",
        "Mohammed Al-Khafajiy",
        "Alexandr Klimchik",
        "Riccardo Polvara",
        "Athanasios Polydoros",
        "Zied Tayeb",
        "Sepher Maleki",
        "Junfeng Gao",
        "Tom Duckett",
        "Mini Rai",
        "Amir Ghalamzan Esfahani"
    ]

    all_articles = []
    df_all = None
    for author_name in lcas_authors:
        logger.info(f"*** processing {author_name}...")
        authors[author_name] = Author(author_name)
        authors[author_name].retrieve()
        if df_all is None:
            df_all = authors[author_name].df
        else:
            df_all = pd.concat([df_all, authors[author_name].df])
        all_articles.extend(authors[author_name].articles)

    print(f"Total number of articles: {len(all_articles)}")
    print(df_all.head())
    print(list(df_all.columns))
    filtered_df = df_all[df_all['online_date'] > pd.Timestamp(datetime(2021, 1, 1)).tz_localize('UTC')]
    
    # Save all data to CSV
    csv_filename = "figshare_articles.csv"
    df_all.to_csv(csv_filename, index=False)
    print(f"Saved all articles to {csv_filename}")

    # Save filtered data to CSV
    filtered_csv_filename = "figshare_articles_since_2021.csv"
    filtered_df.to_csv(filtered_csv_filename, index=False)
    print(f"Saved articles since 2021 to {filtered_csv_filename}")

    # # Create a pivot table with author as rows and count of articles as values
    # pivot_table = pd.pivot_table(filtered_df, 
    #                             index='author', 
    #                             values='id', 
    #                             aggfunc='count')
    
    # # Sort by count in descending order
    # pivot_table = pivot_table.sort_values(by='id', ascending=False)
    
    # # Rename the column to be more descriptive
    # pivot_table.rename(columns={'id': 'article_count'}, inplace=True)
    
    # print("Pivot table of authors and their article counts (after Jan 1, 2021):")
    # print(pivot_table)
    # print(f"Number of articles published after January 1st, 2021: {len(filtered_df)}, {len(df_all)}")

    
if __name__ == "__main__":
    doi2bibtex_test()
    figshare_processing()
