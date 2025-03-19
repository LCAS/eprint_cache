#!/usr/bin/env python
# -*- coding: utf-8 -*-

from requests import get, post
from json import loads
from pprint import pformat
import pandas as pd
from functools import lru_cache, wraps
from datetime import datetime

from logging import getLogger, basicConfig, INFO
import os
from pickle import load, dump

from flatten_dict import flatten

basicConfig(level=INFO)
logger = getLogger(__name__)


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
        self.articles = []
        self.public_html_prefix = "https://repository.lincoln.ac.uk"

    def retrieve_figshare(self):
        self.logger.info(f"retrieving articles for {self.name}")
        self.articles = self.fs.articles_by_user_name(self.name)

        self.logger.info(f"found {len(self.articles)} articles for {self.name}")

    def retrieve_details(self):
        for article in self.articles:
            self.logger.info(f"retrieving details for article {article['id']}")
            article['details'] = self.fs.get_article(article['id'])


    def remove_non_repository(self):
        self.logger.info(f"removing non-repository articles out of {len(self.articles)}")
        self.articles = [a for a in self.articles if a['url_public_html'].startswith(self.public_html_prefix)]
        self.logger.info(f"retained {len(self.articles)} articles")

    def custom_fields_to_dicts(self):
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

    def retrieve_bibtex_from_dois(self):
        from doi2bib import crossref
        for article in self.articles:
            if 'details' not in article:
                continue
            if 'custom_fields' not in article['details']:
                continue
            if "External DOI" not in article['details']['custom_fields']:
                self.logger.info(f"no External DOI field")
                continue
            doi = article['details']['custom_fields']['External DOI']
            #print(type(doi))
            if len(doi) < 1:
                self.logger.info(f"no External DOI")
                continue
            doi = doi[0]
            doi = doi.replace("https://doi.org/","")
            self.logger.info(f"retrieve for DOI {doi}")
            success, bibtex = crossref.get_bib_from_doi(doi)
            if success:
                article['bibtex'] = bibtex
                self.logger.info(bibtex)
    
    def flatten(self):
        new_articles = []
        for a in self.articles:
            new_articles.append(flatten(a, reducer='path'))
        self.articles = new_articles

class BibTeXGenerator:
    
    def __init__(self):
        self.__cache = {}
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

    def _save_cache(self):
        with open(self.cache_file,"wb") as f:
            dump(self.__cache, f)

    def getBibtex(self, article_id, use_cache=True):
        hash_key = f"getBibtex{article_id}"
        if hash_key in self.__cache and use_cache:
            return self.__cache[hash_key]
        else:
            headers = { "Authorization": "token " + self.token } if self.token else {}
            result = get(self.base_url + url, headers=headers, params=params).json()
            self.__cache[hash_key] = result
            self.save_cache()
            return result




if __name__ == "__main__":
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
        "Mini Chakravarthini Rai",
        "Amir Ghalamzan Esfahani"
    ]

    all_articles = []
    df_all = None
    for author_name in lcas_authors:
        logger.info(f"*** processing {author_name}...")
        authors[author_name] = Author(author_name)
        authors[author_name].retrieve_figshare()
        authors[author_name].remove_non_repository()
        authors[author_name].retrieve_details()
        authors[author_name].custom_fields_to_dicts()
        authors[author_name].flatten()
        #df = pd.DataFrame(authors[author_name].articles)
        df = pd.DataFrame.from_dict(authors[author_name].articles)
        df['author'] = author_name
        if df_all is None:
            df_all = df
        else:
            df_all = pd.concat([df_all, df])
        all_articles.extend(authors[author_name].articles)

        #author.retrieve_bibtex_from_dois()
    #print(df_all.columns)
    #print(len(all_articles))
    #print(pformat(all_articles[0]))
    #df = pd.DataFrame(all_articles)
    # Convert published_date to datetime and filter for dates after January 1st, 2021
    df_all['online_date'] = pd.to_datetime(df_all['timeline/firstOnline'], utc=True)
    df_all['online_year'] = df_all['online_date'].apply(
        lambda x: x.year
    )
    df_all['External DOI'] = df_all['details/custom_fields/External DOI'].apply(
        lambda x: x[0].replace("https://doi.org/", "") 
            if isinstance(x, list) and len(x) > 0 else x
    )



    filtered_df = df_all[df_all['online_date'] > pd.Timestamp(datetime(2021, 1, 1)).tz_localize('UTC')]
    
    # Save all data to CSV
    csv_filename = "figshare_articles.csv"
    df_all.to_csv(csv_filename, index=False)
    print(f"Saved all articles to {csv_filename}")

    # Save filtered data to CSV
    filtered_csv_filename = "figshare_articles_since_2021.csv"
    filtered_df.to_csv(filtered_csv_filename, index=False)
    print(f"Saved articles since 2021 to {filtered_csv_filename}")

    # Create a pivot table with author as rows and count of articles as values
    pivot_table = pd.pivot_table(filtered_df, 
                                index='author', 
                                values='id', 
                                aggfunc='count')
    
    # Sort by count in descending order
    pivot_table = pivot_table.sort_values(by='id', ascending=False)
    
    # Rename the column to be more descriptive
    pivot_table.rename(columns={'id': 'article_count'}, inplace=True)
    
    print("Pivot table of authors and their article counts (after Jan 1, 2021):")
    print(pivot_table)
    print(f"Number of articles published after January 1st, 2021: {len(filtered_df)}, {len(df_all)}")

    