"""Explicit live smoke test. Not included in the normal unit-test directory."""
import os
import uuid
import httpx
import pytest
from hr_agent.schema import Answer

@pytest.mark.skipif(not os.getenv('HR_BASE_URL'), reason='HR_BASE_URL is required')
def test_live_endpoint():
    base = os.environ['HR_BASE_URL'].rstrip('/')
    headers = {'X-API-Key':os.environ['HR_EMPLOYEE_API_KEY']}
    if os.getenv('CLOUD_RUN_ID_TOKEN'):
        headers['X-Serverless-Authorization'] = 'Bearer '+os.environ['CLOUD_RUN_ID_TOKEN']
    assert httpx.get(base+'/health',headers=headers,timeout=60).json()['status']=='ok'
    response = httpx.post(base+'/ask',headers=headers,
        json={'question':'What is the carry forward policy?','thread_id':str(uuid.uuid4())},timeout=180)
    response.raise_for_status()
    result = response.json()
    Answer.model_validate({k:v for k,v in result.items() if k!='thread_id'})
    assert result['status']=='answered' and 'LEAVE-02' in result['citations']
