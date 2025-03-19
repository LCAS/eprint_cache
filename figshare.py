#!/usr/bin/env python
# -*- coding: utf-8 -*-

from requests import get, post
from json import loads
from pprint import pformat
from functools import lru_cache, wraps

from logging import getLogger, basicConfig, INFO
import os
from pickle import load, dump
basicConfig(level=INFO)
logger = getLogger(__name__)


class FigShare:
    def __init__(self, token=None, page_size=100):
        self.logger = getLogger("FigShare")
        self.token = token
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

        for article in self.articles:
            self.logger.info(f"retrieving details for article {article['id']}")
            article['details'] = self.fs.get_article(article['id'])

        self.logger.info(f"found {len(self.articles)} articles for {self.name}")

    def remove_non_repository(self):
        self.logger.info(f"removing non-repository articles out of {len(self.articles)}")
        self.articles = [a for a in self.articles if a['url_public_html'].startswith(self.public_html_prefix)]
        self.logger.info(f"retained {len(self.articles)} articles")




if __name__ == "__main__":
    author = Author("Marc Hanheide")
    author.retrieve_figshare()
    author.remove_non_repository()

    logger.info(f"1st article: {pformat(author.articles[0])}")