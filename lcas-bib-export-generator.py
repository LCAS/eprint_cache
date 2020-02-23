#!/usr/bin/env python


# old URL using IDs that is NOT working reliably:
# http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_id%3Acreators_id%3AANY%3AIN%3A002146+801704+801872+801929+003092+002165+001928+802799+002604+504752+504299+002325%7Ctype%3Atype%3AANY%3AEQ%3Aarticle+review+book_section+monograph+conference_item+book+thesis+dataset%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=

staff = [
    'Hanheide, Marc',
    'Duckett, Tom',
    'Sklar, Elizabeth',
    'Saaj',
    'Elgeneidy',
    'Esfahani',
    'Millard, Alan',
    'Yue, Shigang',
    'Neumann, Gerhard',
    'Hanheide, Marc',
    'Bellotto, Nicola',
    'Baxter, Paul',
    'Cielniak, Grzegorz',
    'Cuayahuitl, Heriberto',
    'Fox, Charles',
    'Kucukyilmaz, Ayse'
]

# recent
year = '2010-2030'
year = '2019'

def quote_name(n):
    return '%%22%s%%22' % n.replace(',','%2C').replace(' ','+')

def quote_names(ns):
    return [quote_name(n) for n in ns]


#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced?screen=Search&dataset=archive&_action_search=Search&documents_merge=ALL&documents=&title_merge=ALL&title=&documents.title_merge=ALL&documents.title=&creators_name_merge=ANY&creators_name=Hanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter&creators_id_merge=ALL&creators_id=&abstract_merge=ALL&abstract=&date_online=&date_accepted=&date=2019-&documents.description_merge=ALL&documents.description=&keywords_merge=ALL&keywords=&subjects_merge=ANY&divisions_merge=ANY&editors_name_merge=ALL&editors_name=&refereed=EITHER&publication_merge=ALL&publication=&projects_merge=ALL&projects=&satisfyall=ALL&order=-date%2Fcreators_name%2Ftitle
#http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lincoln_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_name%3Acreators_name%3AANY%3AEQ%3AHanheide+Duckett+Saaj+Sklar+Yue+Bellotto+Baxter%7Cdate%3Adate%3AALL%3AEQ%3A2019-%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=&cache=11353462

url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s%%7Cdate%%3Adate%%3AALL%%3AEQ%%3A%s'

print url_pattern % ('%2C+'.join(quote_names(staff)), year)
