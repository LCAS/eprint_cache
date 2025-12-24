#!/usr/bin/env python
# -*- coding: utf-8 -*-

from requests import get, post
import shelve
import time
import os
from logging import getLogger, INFO


class FigShare:
    def __init__(self, page_size=100, rate_limit_delay=1.0, max_retries=5):
        self.logger = getLogger("FigShare")
        self.token = os.getenv('FIGSHARE_TOKEN')
        if self.token:
            self.logger.info("Figshare API: Using authenticated requests")
        else:
            self.logger.warning("Figshare API: No authentication token found - using anonymous requests (may hit rate limits or receive 403 errors)")
        self.page_size = page_size
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.base_url = "https://api.figshare.com/v2"
        
        if self.rate_limit_delay > 0:
            self.logger.info(f"Rate limiting enabled: {self.rate_limit_delay} second delay between API requests")

        # Use shelve for persistent caching
        self.cache_file = "figshare_cache.db"

        with shelve.open(self.cache_file) as cache:
            self.logger.info(f"Figshare API: Using cache file {self.cache_file} with {len(cache.keys())} entries")
            for key in list(cache.keys()):
                self.logger.debug(f"  existing cache key: {key}")


    def __init_params(self):
        return {
            "page_size": self.page_size
        }

    def __handle_403_error(self, url, method="GET", response_text=""):
        """Handle 403 Forbidden errors with helpful messages"""
        if not self.token:
            self.logger.error(f"403 Forbidden for {method} {self.base_url + url}: "
                            f"Authentication required. Set FIGSHARE_TOKEN environment variable. "
                            f"See README.md for instructions.")
        else:
            self.logger.error(f"403 Forbidden for {method} {self.base_url + url}: "
                            f"Token may be invalid or lack permissions. "
                            f"Check token in Figshare account settings.")
        if response_text:
            self.logger.error(f"Response text: {response_text}")

    def __get(self, url, params=None, use_cache=True):
        hash_key = f"GET{url}{'?' + str(params) if params else ''}"
        
        with shelve.open(self.cache_file) as cache:
            if hash_key in cache and use_cache:
                self.logger.info(f"Cache hit for GET {url}")
                return cache[hash_key]
            
            headers = { "Authorization": "token " + self.token } if self.token else {}
            
            # Retry logic for 403 errors
            for attempt in range(self.max_retries):
                response = get(self.base_url + url, headers=headers, params=params)
                
                # Handle 403 Forbidden errors with retry logic
                if response.status_code == 403:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                        wait_time = 2 ** attempt
                        self.logger.warning(f"403 Forbidden for GET {url} (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed, log error and return
                        self.__handle_403_error(url, "GET", response.text)
                        return {}
                
                # Success - break out of retry loop
                break

            # Rate limiting: sleep after each API request
            if self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)
            
            # Check if response is valid and contains JSON
            if response.ok and response.headers.get('Content-Type', '').lower().startswith('application/json') and response.text.strip():
                result = response.json()
                cache[hash_key] = result
                self.logger.debug(f"Cached result for GET {url}")
                return result
            else:
                self.logger.warning(f"Received empty or invalid JSON response for GET {self.base_url + url} (status: {response.status_code})")
                return {}

    def __post(self, url, params=None, use_cache=True):
        hash_key = f"POST{url}{'?' + str(params) if params else ''}"
        
        with shelve.open(self.cache_file) as cache:
            if hash_key in cache and use_cache:
                self.logger.debug(f"Cache hit for POST {url}")
                return cache[hash_key]
            
            headers = { "Authorization": "token " + self.token } if self.token else {}
            
            # Retry logic for 403 errors
            for attempt in range(self.max_retries):
                response = post(self.base_url + url, headers=headers, json=params)
                
                # Handle 403 Forbidden errors with retry logic
                if response.status_code == 403:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                        wait_time = 2 ** attempt
                        self.logger.warning(f"403 Forbidden for POST {url} (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed, log error and return
                        self.__handle_403_error(url, "POST", response.text)
                        return []
                
                # Success - break out of retry loop
                break
            
            # Rate limiting: sleep after each API request
            if self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)
            
            # Check if response is valid and contains JSON
            if response.ok and response.headers.get('Content-Type', '').lower().startswith('application/json') and response.text.strip():
                result = response.json()
                cache[hash_key] = result
                self.logger.debug(f"Cached result for POST {url}")
                return result
            else:
                self.logger.warning(f"Received empty or invalid JSON response for POST {self.base_url + url} (status: {response.status_code})")
                return []

        
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
