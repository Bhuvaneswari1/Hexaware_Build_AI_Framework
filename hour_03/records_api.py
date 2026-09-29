"""Small HTTP boundary for the TOC's leave-balance API exercise."""
import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from hr_agent.business import balance

app = FastAPI(title='Synthetic HR records API')

@app.get('/leave-balance')
def leave_balance(x_records_key: str = Header(default='')):
    expected = os.getenv('HR_RECORDS_API_KEY')
    if not expected or not secrets.compare_digest(expected,x_records_key):
        raise HTTPException(401,detail='Invalid records API key')
    return balance('E001')
