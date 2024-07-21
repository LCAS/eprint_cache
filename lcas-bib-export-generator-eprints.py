#!/usr/bin/env python

from requests import get
from sys import stderr

# old URL using IDs that is NOT working reliably:
# http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_id%3Acreators_id%3AANY%3AIN%3A002146+801704+801872+801929+003092+002165+001928+802799+002604+504752+504299+002325%7Ctype%3Atype%3AANY%3AEQ%3Aarticle+review+book_section+monograph+conference_item+book+thesis+dataset%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=

staff = [
    'Hanheide, Marc',
    'Duckett, Tom',
    'Sklar, Elizabeth',
    'Saaj, Mini',
    'Elgeneidy',
    'Esfahani',
    'Bosilj',
    'Calisti, Marcello',
    'Das, Gautham',
    'Gao, Junfeng',
    'Guevara, Leonardo',
    'Maleki, Sepehr',
    'Al-Khafajiy',
    'Polydoros', 
    'Yue, Shigang',
    'Bellotto, Nicola',
    'Baxter, Paul',
    'Cielniak, Grzegorz',
    'Cuayahuitl, Heriberto',
    'Fox, Charles',
    'Parsons, Simon',
    'Pearson, Simon',
    'Bochtis',
    'Polvara, Riccardo',
    'del Duchetto, Francesco',
    'Klimchik, Alexandr',
    'Rai, Mini',
    'Harman, Helen',
    'Zied, Tayeb'
]

# recent
years = list(range(2012,2025))

def quote_name(n):
    return '%%22%s%%22' % n.replace(',','%2C').replace(' ','+')

def quote_names(ns):
    return [quote_name(n) for n in ns]


#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced?screen=Search&dataset=archive&_action_search=Search&documents_merge=ALL&documents=&title_merge=ALL&title=&documents.title_merge=ALL&documents.title=&creators_name_merge=ANY&creators_name=Hanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter&creators_id_merge=ALL&creators_id=&abstract_merge=ALL&abstract=&date_online=&date_accepted=&date=2019-&documents.description_merge=ALL&documents.description=&keywords_merge=ALL&keywords=&subjects_merge=ANY&divisions_merge=ANY&editors_name_merge=ALL&editors_name=&refereed=EITHER&publication_merge=ALL&publication=&projects_merge=ALL&projects=&satisfyall=ALL&order=-date%2Fcreators_name%2Ftitle
#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_name%3Acreators_name%3AANY%3AEQ%3AHanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter%7Cdate%3Adate%3AALL%3AEQ%3A2019-%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=&cache=11353462

url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s%%7Cdate%%3Adate%%3AALL%%3AEQ%%3A%s'


'https://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_AllRSS.rss?screen=Search&amp;dataset=archive&amp;_action_export=1&amp;output=AllRSS&amp;exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_name%3Acreators_name%3AALL%3AEQ%3AHanheide'

rss_url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_RSS2.xml?screen=Search&dataset=archive&_action_export=1&output=RSS2&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s'


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

years.reverse()

with open('wordpress.html','w') as html_file:
    print('<p>Download the <a href="%s" target="_blank">BibTeX file of all L-CAS publications</a></p>' % (
        pubs_year_url('', staff)
    ), file=html_file)

    with open('lcas.bib', 'w') as all_bib:
        bibtex = get_file(pubs_year_url('', staff))
        all_bib.write(bibtex)

    for year in years:
        print("<h2>%s</h2>" % str(year), file=html_file)
        bibtex_url = pubs_year_url(year, staff)
        print('generating for year %d using %s' % (year, bibtex_url), file=stderr)
        print(shortcode_pattern % (
            bibtex_url,
            highlight_names(staff),
            highlight_names(staff)
        ), file=html_file)

        bibtex = get_file(bibtex_url)
        with open('%d.bib' % year, 'w') as bibtex_file:
            bibtex_file.write(bibtex)


print('-------------------------------')
with open('lcas.rss','w') as rss_file:
    rssdata = get_file(rss_url(staff))
    rss_file.write(rssdata)
    print(rss_url(staff))


