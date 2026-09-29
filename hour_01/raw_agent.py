"""Run the function-call protocol without an agent framework."""
import argparse
import json
from openai import OpenAI
from langsmith.wrappers import wrap_openai
from hr_agent.config import live
from hr_agent.business import balance, days
import os

def run(question, employee='E001'):
    if not live():
        raise ValueError('Raw model function calling requires HR_MODE=live and OPENAI_API_KEY. Use hour_01.app for demo mode.')
    tools = [
        {'type':'function','function':{'name':'leave_balance','description':'Get current employee annual leave balance',
         'parameters':{'type':'object','properties':{},'required':[],'additionalProperties':False},'strict':True}},
        {'type':'function','function':{'name':'date_calculator','description':'Inclusive Monday-Friday working day count',
         'parameters':{'type':'object','properties':{'start':{'type':'string'},'end':{'type':'string'}},
                       'required':['start','end'],'additionalProperties':False},'strict':True}}]
    client = wrap_openai(OpenAI(timeout=60,max_retries=2))
    messages = [{'role':'system','content':'Use tools for leave balances and dates. Give a concise answer from observations. You cannot apply leave.'},
                {'role':'user','content':question}]
    for turn in range(8):
        msg = client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini-2025-04-14'),
                                             messages=messages,tools=tools).choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            print(json.dumps({'answer':msg.content},indent=2)); return
        for call in msg.tool_calls:
            arguments = json.loads(call.function.arguments)
            if call.function.name == 'leave_balance' and arguments == {}:
                result = balance(employee)
            elif call.function.name == 'date_calculator':
                result = {'working_days':days(**arguments)}
            else:
                raise ValueError('Unknown tool or invalid arguments')
            print(json.dumps({'step':turn+1,'tool':call.function.name,'arguments':arguments,'observation':result}))
            messages.append({'role':'tool','tool_call_id':call.id,'content':json.dumps(result)})
    raise RuntimeError('Exceeded eight model turns')

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('question'); p.add_argument('--employee',default='E001')
    a = p.parse_args(); run(a.question,a.employee)
