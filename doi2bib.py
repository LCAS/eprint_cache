#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib.request
import requests
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase
import shelve
from logging import getLogger, INFO


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
                response = requests.get(url)
                # Check if response is valid and contains JSON
                if response.ok and response.headers.get('Content-Type', '').lower().startswith('application/json') and response.text.strip():
                    result = response.json()
                    short_doi = result['ShortDOI']
                else:
                    self.logger.warning(f"Received empty or invalid JSON response for {doi} from {url} (status: {response.status_code})")
                    return None
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
            if not response.ok:
                self.logger.warning(f"failed to get bibtex for {doi}, status code {response.status_code}")
                return ""
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
