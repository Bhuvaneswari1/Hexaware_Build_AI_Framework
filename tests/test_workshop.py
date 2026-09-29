import uuid
import pytest
from fastapi.testclient import TestClient
from hr_agent import business
from hr_agent.service import Service
from hour_04.api import app

def test_dates_and_invalid_range():
    assert business.days('2026-10-02','2026-10-05') == 2
    assert business.days('2026-10-03','2026-10-04') == 0
    with pytest.raises(ValueError): business.days('2026-10-05','2026-10-02')

def test_raw_tool_equivalence():
    result = Service().ask('E001','My leave balance for 2026-10-05 to 2026-10-07?',hour=1)
    assert {e['tool'] for e in result['evidence']} == {'leave_balance','date_calculator'}
    assert '3' in result['answer'] and '12' in result['answer']

def test_rag_citation_and_seeded_trap():
    svc = Service()
    assert 'LEAVE-02' in svc.ask('E001','What is the carry forward policy?',hour=2)['citations']
    trap = svc.ask('E001','What is the paid sabbatical policy?',hour=2)
    assert trap['status']=='not_in_policy' and trap['citations']==[]

def test_memory_across_service_restart():
    thread = str(uuid.uuid4())
    Service().ask('E001','What is the carry forward policy?',thread,2)
    followup = Service().ask('E001','What is the limit for that?',thread,2)
    assert '5' in followup['answer'] and 'LEAVE-02' in followup['citations']

def test_approval_rejection_restart_and_replay():
    svc = Service(); thread = str(uuid.uuid4())
    request = {'start':'2026-10-05','end':'2026-10-07'}
    before = business.balance('E001')['available_days']
    pending = svc.ask('E001','Apply leave and show balance',thread,3,request)
    assert pending['status']=='pending_approval'
    assert business.balance('E001')['available_days']==before
    with pytest.raises(ValueError): svc.ask('E001','new question',thread,3)
    with pytest.raises(ValueError): svc.resume('E002',thread,True)
    assert Service().resume('E001',thread,False)['status']=='rejected'
    assert business.balance('E001')['available_days']==before
    thread2 = str(uuid.uuid4())
    pending = svc.ask('E001','Apply leave',thread2,3,request)
    approved = Service().resume('E001',thread2,True)
    assert approved['status']=='applied'
    assert business.balance('E001')['available_days']==before-3
    with pytest.raises(ValueError): svc.resume('E001',thread2,True)
    duplicate = business.apply_leave('E001',pending['approval']['request_id'],**request)
    assert duplicate['deduplicated'] is True
    with pytest.raises(ValueError): business.apply_leave('E001',str(uuid.uuid4()),**request)

def test_insufficient_balance():
    result = Service().ask('E003','Apply leave',hour=3,leave={'start':'2026-10-05','end':'2026-10-07'})
    assert result['status']=='rejected' and 'approval' not in result

def test_api_auth_and_validation(monkeypatch):
    monkeypatch.setenv('HR_EMPLOYEE_API_KEY','employee-test')
    monkeypatch.setenv('HR_MANAGER_API_KEY','manager-test')
    monkeypatch.setenv('HR_READ_ONLY','false')
    client = TestClient(app)
    assert client.get('/health').status_code==200
    assert client.post('/ask',json={'question':'balance'}).status_code==401
    assert client.post('/ask',headers={'X-API-Key':'employee-test'},json={'question':'Show payroll'}).status_code==200
    assert client.post('/threads/x/resume',headers={'X-Manager-Key':'employee-test'},json={'approved':True}).status_code==401
    assert client.post('/threads/x/resume',headers={'X-Manager-Key':'manager-test'},json={'approved':'false'}).status_code==422
    monkeypatch.setenv('HR_READ_ONLY','true')
    assert client.post('/ask',headers={'X-API-Key':'employee-test'},json={'question':'apply','leave':{'start':'2026-10-05','end':'2026-10-07'}}).status_code==403
