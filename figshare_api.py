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

    def articles_by_author(self, author_name, user_id=None, institution_id=None, use_cache=True):
        """Search for articles by author name with optional institution filtering.
        
        Uses the Figshare search API with the :author: search operator and optional
        institution parameter. Note: Figshare's search API does not support searching
        by author_id directly, so we use the author name for search and apply
        institution filtering to narrow results.
        
        Args:
            author_name: The author's full name to search for (required)
            user_id: Figshare user ID (optional, used only for logging/reference)
            institution_id: Institution ID to filter articles (optional, recommended
                          for more precise results when available)
            use_cache: Whether to use cached results (default: True)
        
        Returns:
            List of article dictionaries matching the search criteria. Each article
            contains metadata like id, title, authors, DOI, etc.
        
        Example:
            articles = fs.articles_by_author(
                "Marc Hanheide", 
                user_id=17159320,
                institution_id=1068
            )
        """
        params = self.__init_params()
        
        # Use :author: search operator with author name
        # This is the only reliable way to search by author in Figshare API
        params["search_for"] = f':author: "{author_name}"'
        
        # Add institution filter as direct parameter if provided
        # This significantly narrows results when multiple authors share the same name
        if institution_id:
            params["institution"] = institution_id
            self.logger.info(f"Filtering by institution_id: {institution_id}")
        
        # Paginate through all results
        page = 1
        articles = []
        while True:
            params["page"] = page
            if user_id:
                self.logger.info(f"retrieving page {page} for {author_name} (user_id: {user_id})")
            else:
                self.logger.info(f"retrieving page {page} for {author_name}")
            current_page_articles = self.__post("/articles/search", params=params, use_cache=use_cache)
            page += 1
            if len(current_page_articles) == 0:
                break
            articles += current_page_articles
        
        if user_id:
            self.logger.info(f"found {len(articles)} articles for {author_name} (user_id: {user_id})")
        else:
            self.logger.info(f"found {len(articles)} articles for {author_name}")

        return articles
    
    def articles_by_user_name(self, user_name, use_cache=True):
        """Search for articles by author name without additional filtering.
        
        This is a simpler version of articles_by_author() without institution
        filtering or user_id tracking. Use articles_by_author() for more precise
        searches when institution_id is available.
        
        Args:
            user_name: The author's full name to search for
            use_cache: Whether to use cached results (default: True)
        
        Returns:
            List of article dictionaries matching the author name
        """
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
    
    def search_authors(self, params, use_cache=True):
        """Search for authors using the Figshare account API.
        
        Args:
            params: Dictionary with search parameters (search, orcid, is_active, 
                   is_public, group_id, institution_id)
            use_cache: Whether to use cached results
        
        Returns:
            List of author dictionaries matching the search criteria
        """
        self.logger.info(f"Searching for authors with params: {params}")
        return self.__post("/account/authors/search", params=params, use_cache=use_cache)
