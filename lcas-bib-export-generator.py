#!/usr/bin/env python


# old URL using IDs that is NOT working reliably:
# http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%7C1%7C-date%2Fcreators_name%2Ftitle%7Carchive%7C-%7Ccreators_id%3Acreators_id%3AANY%3AIN%3A002146+801704+801872+801929+003092+002165+001928+802799+002604+504752+504299+002325%7Ctype%3Atype%3AANY%3AEQ%3Aarticle+review+book_section+monograph+conference_item+book+thesis+dataset%7C-%7Ceprint_status%3Aeprint_status%3AANY%3AEQ%3Aarchive%7Cmetadata_visibility%3Ametadata_visibility%3AANY%3AEQ%3Ashow&n=

staff = [
    'Hanheide, Marc',
    'Duckett, Tom',
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


def quote_name(n):
    return '%%22%s%%22' % n.replace(',','%2C').replace(' ','+')

def quote_names(ns):
    return [quote_name(n) for n in ns]



url_pattern='http://eprints.lincoln.ac.uk/cgi/search/archive/advanced/export_lirolem_BibTeX.bib?screen=Search&dataset=archive&_action_export=1&output=BibTeX&exp=0%%7C1%%7C-%%7Ccreators_name%%3Acreators_name%%3AANY%%3AIN%%3A%s'

print url_pattern % '%2C+'.join(quote_names(staff))
