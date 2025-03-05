#!/usr/bin/env python

from orcid_to_bibtex import get_orcid_works, parse_and_format_bib
from asyncio import run

from requests import get
from sys import stderr
from json import dumps, loads


# recent
#years = list(range(2012,2025))

class BibGenerator:
    def __init__(self, load_from=None):
        from config import Config
        self.staff_dict = Config.staff_dict
        if load_from:
            with open(load_from, 'r') as staff_file:
                self.staff_dict = loads(staff_file.read())
        self.shortcode_pattern = (
            '[bibfilter group="firstauthor" group_order="desc" format="ieee" order=asc limit=1000 '
            'file="%s" '
            'timeout=60000 '
            'highlight="%s" '
            'sortauthors=1 '
            'allow="incollection,mastersthesis,article,conference,techreport,inproceedings" '
            'author="%s"'
            ']'
        )

    def retrieve_profiles(self):
        from requests import get
        from json import loads

        for staff_id, staff in self.staff_dict.items():
            if 'sys_id' not in staff or staff['sys_id'] is None:
                print(f"no sys_id for {staff_id}", file=stderr)
                continue
            url = f"https://staff.lincoln.ac.uk/profile/{staff['sys_id']}/data/"
            response = get(url)
            if response.status_code != 200:
                print(f"error retrieving profile for {staff_id} from {url}", file=stderr)
                continue
            staff.update(loads(response.text)['person'])
            print(f"retrieved profile for {staff_id} from {url}", file=stderr)
        #pprint(self.staff_dict, stream=stderr)

    def quote_name(self, n):
        return '%%22%s%%22' % n.replace(',','%2C').replace(' ','+')

    def quote_names(self, ns):
        return [self.quote_name(n) for n in ns]

    def highlight_names(self, names):
        filtered = [s.split(', ')[0] for s in names]
        return '|'.join(filtered)

    def get_file(self, bibtex_url):
        return get(bibtex_url, verify=False, timeout=200).text

    def parse_bib(self, bib):
        from bibtexparser import loads
        return loads(bib).entries_dict

    async def retrieve_bibs(self, max_process=None):

        processed = 0
        for staff_id, staff in self.staff_dict.items():
            staff['bib'] = []
            try:
                if 'orcid' in staff and staff['orcid']:
                    orcid = staff['orcid']
                    print(f"retrieve bib for {staff_id} with orcid id {orcid}", file=stderr)
                    staff_bib = await get_orcid_works(orcid, max_dls=20)
                    staff['bib'] = list(set(staff_bib))
                else:
                    print(f"no orcid for {staff_id}", file=stderr)
                processed += 1
                if max_process and processed >= max_process:
                    break
            except Exception as e:
                print(f"error processing staff {staff_id}: {str(e)}", file=stderr)
                print(f"execption details: {e}", file=stderr)

    def save_staff(self, filename="staff.json"):
        with open(filename, 'w') as staff_file:
            staff_file.write(dumps(self.staff_dict, indent=2))

    def generate_bibs(self):
        bibs = []
        for staff_id, staff in self.staff_dict.items():
            if 'bib' not in staff:
                print(f"no bib for {staff_id}", file=stderr)
                continue
            staff_bib = staff['bib']
            bibs.extend(staff_bib)
            with open('%s.bib' % staff_id, 'w') as bib_file:
                bib_file.write(parse_and_format_bib("".join(set(staff_bib))))

        bib = "".join(set(bibs))            
        with open('lcas.bib', 'w') as all_bib:
            all_bib.write(parse_and_format_bib(bib))
        with open('lcas-bib.json', 'w') as jsonfile:
            jsonfile.write(dumps(self.parse_bib(parse_and_format_bib(bib)), indent=2))

        with open('wordpress.html','w') as html_file:
            names = self.highlight_names([s['surname'] for i, s in self.staff_dict.items()])
            print(self.shortcode_pattern % (
                'https://raw.githubusercontent.com/LCAS/eprint_cache/main/lcas.bib',
                names, names
            ), file=html_file)

async def main():
    #generator = BibGenerator(load_from='staff.json')
    generator = BibGenerator()
    generator.retrieve_profiles()
    await generator.retrieve_bibs(max_process=1)
    generator.generate_bibs()
    generator.save_staff()

if __name__ == "__main__":
    run(main())
