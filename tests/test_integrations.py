import json
import os
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from hr_agent.schema import Answer
from hr_agent.tools import tools_for
from hour_03.records_api import app as records_app
from hour_04.evaluate import structured

def test_records_api_and_http_adapter(monkeypatch):
    monkeypatch.setenv('HR_RECORDS_API_KEY','record-test')
    api = TestClient(records_app)
    assert api.get('/leave-balance').status_code == 401
    payload = api.get('/leave-balance',headers={'X-Records-Key':'record-test'}).json()
    assert payload['employee_id']=='E001' and isinstance(payload['available_days'],int)
    monkeypatch.setenv('HR_RECORDS_API_URL','https://records.example.test')
    def get(url,headers,timeout):
        assert url.endswith('/leave-balance') and headers['X-Records-Key']=='record-test'
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload)
    monkeypatch.setattr('httpx.get',get)
    tool = next(t for t in tools_for('E001',3) if t.name=='leave_balance')
    assert tool.invoke({}) == payload
    other = next(t for t in tools_for('E002',3) if t.name=='leave_balance')
    with pytest.raises(ValueError): other.invoke({})

def test_structured_evaluator_rejects_bad_contract():
    ref = {'expected_status':'answered','required_citation':'LEAVE-02'}
    good = Answer(status='answered',answer='Carry 5 days',citations=['LEAVE-02']).model_dump()
    assert structured(good,ref)['score']==1
    assert structured({**good,'citations':[]},ref)['score']==0
    assert structured({**good,'unexpected':True},ref)['score']==0
    trap = Answer(status='not_in_policy',answer='not in policy').model_dump()
    assert structured(trap,{'expected_status':'not_in_policy'})['score']==1
    assert structured({**trap,'answer':'Maybe 6 months'},{'expected_status':'not_in_policy'})['score']==0

def test_raw_function_call_protocol_with_fake_client(monkeypatch,capsys):
    from hour_01 import raw_agent
    class Message:
        def __init__(self,calls=None,content=None):
            self.tool_calls=calls; self.content=content
        def model_dump(self,**kwargs):
            result = {'role':'assistant','content':self.content}
            if self.tool_calls:
                result['tool_calls']=[{'id':c.id,'type':'function','function':{'name':c.function.name,'arguments':c.function.arguments}} for c in self.tool_calls]
            return result
    calls = [SimpleNamespace(id='a',function=SimpleNamespace(name='leave_balance',arguments='{}')),
             SimpleNamespace(id='b',function=SimpleNamespace(name='date_calculator',arguments='{"start":"2026-10-05","end":"2026-10-07"}'))]
    sequence = [Message(calls),Message(content='Three working days requested.')]
    def create(**kwargs):
        if len(sequence)==1:
            observations = [m for m in kwargs['messages'] if m['role']=='tool']
            assert {m['tool_call_id'] for m in observations}=={'a','b'}
            assert json.loads(observations[1]['content'])['working_days']==3
        return SimpleNamespace(choices=[SimpleNamespace(message=sequence.pop(0))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(raw_agent,'live',lambda:True)
    monkeypatch.setattr(raw_agent,'OpenAI',lambda **kw:client)
    monkeypatch.setattr(raw_agent,'wrap_openai',lambda c:c)
    raw_agent.run('Check balance and dates')
    assert 'Three working days requested' in capsys.readouterr().out
