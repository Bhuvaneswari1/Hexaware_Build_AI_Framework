"""Read-only CSV questions -> CSV answers, useful for HR helpdesk triage."""
import argparse
import csv
import json
from pathlib import Path
from .service import Service

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input',type=Path,default=Path('data/sample_questions.csv'))
    p.add_argument('--output',type=Path,default=Path('.runtime/batch_answers.csv'))
    args = p.parse_args()
    if args.input.resolve()==args.output.resolve():
        p.error('Use a separate output file')
    svc = Service(); args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.input.open(newline='') as source, args.output.open('w',newline='') as dest:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(dest,fieldnames=['case_id','status','answer','citations'])
        writer.writeheader()
        for row in reader:
            result = svc.ask(row['employee_id'],row['question'])
            writer.writerow({'case_id':row['case_id'],**{k:json.dumps(result[k]) if k=='citations' else result[k]
                                                      for k in ['status','answer','citations']}})
    print(f'Wrote {args.output}')

if __name__ == '__main__':
    main()
