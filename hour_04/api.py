import os
import secrets
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field, StrictBool
from hr_agent.service import Service
from hr_agent.schema import LeaveRequest

app = FastAPI(title='HR Agent Workshop', version='1.0')
service = Service()

def check(actual, variable):
    expected = os.getenv(variable)
    if not expected:
        raise HTTPException(503, detail=f'{variable} is not configured')
    if not secrets.compare_digest(actual or '', expected):
        raise HTTPException(401, detail='Invalid API key')

def employee(x_api_key: Annotated[str | None, Header()] = None):
    check(x_api_key,'HR_EMPLOYEE_API_KEY')
    return 'E001'  # Deliberate single-employee workshop identity, bound server-side.

def manager(x_manager_key: Annotated[str | None, Header()] = None):
    check(x_manager_key,'HR_MANAGER_API_KEY')

class Ask(BaseModel):
    question: str = Field(min_length=1,max_length=2000)
    thread_id: str | None = Field(default=None,min_length=1,max_length=100)
    leave: LeaveRequest | None = None

class Resume(BaseModel):
    approved: StrictBool

@app.get('/health')
def health():
    return {'status':'ok','mode':os.getenv('HR_MODE','demo')}

@app.post('/ask')
def ask(body: Ask, identity=Depends(employee)):
    if body.leave and os.getenv('HR_READ_ONLY','false').lower() == 'true':
        raise HTTPException(403,detail='Leave writes disabled for this deployment')
    try:
        return service.ask(identity,body.question,body.thread_id,3,
                           body.leave.model_dump(mode='json') if body.leave else None)
    except ValueError as exc:
        raise HTTPException(400,detail=str(exc)) from exc

@app.post('/threads/{thread_id}/resume', dependencies=[Depends(manager)])
def resume(thread_id: str, body: Resume):
    if os.getenv('HR_READ_ONLY','false').lower() == 'true':
        raise HTTPException(403,detail='Leave writes disabled for this deployment')
    try:
        return service.resume('E001',thread_id,body.approved)
    except ValueError as exc:
        raise HTTPException(409,detail=str(exc)) from exc
