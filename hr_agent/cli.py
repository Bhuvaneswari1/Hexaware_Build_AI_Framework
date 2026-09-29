import argparse
import json
from .service import Service

def main(hour):
    parser = argparse.ArgumentParser()
    parser.add_argument('question', nargs='?', default='What is my leave balance?')
    parser.add_argument('--employee', default='E001')
    parser.add_argument('--thread')
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--resume', choices=['approve','reject'])
    args = parser.parse_args()
    if bool(args.start) != bool(args.end):
        parser.error('Provide both --start and --end')
    service = Service()
    if args.resume:
        if hour < 3 or not args.thread:
            parser.error('Resume needs Hour 3 and --thread')
        result = service.resume(args.employee,args.thread,args.resume=='approve')
    else:
        leave = {'start':args.start,'end':args.end} if args.start else None
        result = service.ask(args.employee,args.question,args.thread,hour,leave)
    print(json.dumps(result,indent=2))
