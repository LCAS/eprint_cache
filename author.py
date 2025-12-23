#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import shelve
import re
from logging import getLogger, INFO, DEBUG
from flatten_dict import flatten

from figshare_api import FigShare
from doi2bib import doi2bib
from doi_utils import guess_doi_from_crossref


class Author:
    def __init__(self, name, debug=False, rate_limit_delay=1.0, max_retries=5):
        self.logger = getLogger("Author")
        if debug:
            self.logger.setLevel(DEBUG)
        self.name = name
        self.fs = FigShare(rate_limit_delay=rate_limit_delay, max_retries=max_retries)
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
        if 'title' not in article or not article['title']:
            self.logger.warning("No title found for article, can't guess DOI")
            return None
        
        title = article['title']
        author = article['author']
        
        return guess_doi_from_crossref(title, author)


    def _retrieve_bibtex_from_dois(self):
        if self.df is None:
            self.logger.warning(f"no dataframe found for {self.name}, can't continue")
            return
        doi2bibber = doi2bib()
        # iterate over all rows in the dataframe self.df
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
        self._retrieve_details(use_cache=True)
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
