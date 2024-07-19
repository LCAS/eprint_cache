#!/usr/bin/env python

from orcid_to_bibtex import get_orcid_works, parse_and_format_bib
from asyncio import run

from requests import get
from sys import stderr


# recent
#years = list(range(2012,2025))

def quote_name(n):
    return '%%22%s%%22' % n.replace(',','%2C').replace(' ','+')

def quote_names(ns):
    return [quote_name(n) for n in ns]


#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced?screen=Search&dataset=archive&_action_search=Search&documents_merge=ALL&documents=&title_merge=ALL&title=&documents.title_merge=ALL&documents.title=&creators_name_merge=ANY&creators_name=Hanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter&creators_id_merge=ALL&creators_id=&abstract_merge=ALL&abstract=&date_online=&date_accepted=&date=2019-&documents.description_merge=ALL&documents.description=&keywords_merge=ALL&keywords=&subjects_merge=ANY&divisions_merge=ANY&editors_name_merge=ALL&editors_name=&refereed=EITHER&publication_merge=ALL&publication=&projects_merge=ALL&projects=&satisfyall=ALL&order=-date%2Fcreators_name%2Ftitle
#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_name%3Acreators_name%3AANY%3AEQ%3AHanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter%7Cdate%3Adate%3AALL%3AEQ%3A2019-%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=&cache=11353462

# url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s%%7Cdate%%3Adate%%3AALL%%3AEQ%%3A%s'


# 'https://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_AllRSS.rss?screen=Search&amp;dataset=archive&amp;_action_export=1&amp;output=AllRSS&amp;exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_name%3Acreators_name%3AALL%3AEQ%3AHanheide'

# rss_url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_RSS2.xml?screen=Search&dataset=archive&_action_export=1&output=RSS2&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s'


def highlight_names(names):
    ret = ''
    filtered = [s.split(', ')[0] for s in names]
    return '|'.join(filtered)

shortcode_pattern=(
    '[bibfilter group="firstauthor" group_order="desc" format="ieee" order=asc limit=1000 '
    'file="%s" '
    'timeout=60000 '
    'highlight="%s" '
    'sortauthors=1 '
    'allow="incollection,mastersthesis,article,conference,techreport,inproceedings" '
    'author="%s"'
    ']'
)

def pubs_year_url(year, staff):
    return url_pattern % ('%2C+'.join(quote_names(staff)), str(year))

def rss_url(staff):
    return rss_url_pattern % ('%2C+'.join(quote_names(staff)))

def get_file(bibtex_url):
    return get(bibtex_url, verify=False, timeout=200).text

#years.reverse()
async def main():

    staff_dict = {
        'Hanheide, Marc': '0000-0001-7728-1849',
        'Duckett, Tom': None,
        'Sklar, Elizabeth': None,
        'Saaj, Mini': None,
        'Elgeneidy': None,
        'Esfahani': None,
        'Bosilj': None,
        'Calisti, Marcello': None,
        'Das, Gautham': None,
        'Gao, Junfeng': None,
        'Guevara, Leonardo': None,
        'Maleki, Sepehr': None,
        'Al-Khafajiy': None,
        'Polydoros': None, 
        'Yue, Shigang': None,
        'Bellotto, Nicola': None,
        'Baxter, Paul': None,
        'Cielniak, Grzegorz': '0000-0002-6299-8465',
        'Cuayahuitl, Heriberto': None,
        'Fox, Charles': None,
        'Parsons, Simon': None,
        'Pearson, Simon': None,
        'Bochtis': None,
        'Polvara, Riccardo': None,
        'del Duchetto, Francesco': None,
        'Klimchik, Alexandr': None,
        'Rai, Mini': None,
        'Harman, Helen': None,
        'Zied, Tayeb': None
    }


    with open('wordpress.html','w') as html_file:

        with open('lcas.bib', 'w') as all_bib:
            bibs = []
            for (staff, orcid) in staff_dict.items():
                if orcid:
                    print('process staff %s with id %s' % (staff, orcid), file=stderr)
                    bibs.extend(await get_orcid_works(orcid, max_dls=5))
            bib = "".join(set(bibs))            
            all_bib.write(
                parse_and_format_bib(bib)
            )

        print(shortcode_pattern % (
            'https://raw.githubusercontent.com/LCAS/eprint_cache/main/lcas.bib',
            highlight_names(staff_dict.keys()),
            highlight_names(staff_dict.keys())
        ), file=html_file)





if __name__ == "__main__":
    run(main())