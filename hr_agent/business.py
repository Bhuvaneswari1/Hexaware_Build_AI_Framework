"""Deterministic data access and transactional mock leave writes."""
import csv
import sqlite3
from datetime import date, timedelta
from .config import DATA, RUNTIME
from .schema import LeaveRequest

def rows(name):
    with (DATA / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def record(name, employee):
    matches = [r for r in rows(name) if r['employee_id'] == employee]
    if len(matches) != 1:
        raise ValueError('Unknown or duplicate employee ID')
    return matches[0]

def days(start, end):
    request = LeaveRequest(start=start, end=end)
    return sum((request.start + timedelta(days=i)).weekday() < 5
               for i in range((request.end - request.start).days + 1))

def connection():
    db = sqlite3.connect(RUNTIME / 'leave.sqlite', timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, employee TEXT, start TEXT, end TEXT, days INTEGER)')
    return db

def balance(employee):
    base = int(record('employees.csv', employee)['annual_leave_days'])
    with connection() as db:
        used = db.execute('SELECT coalesce(sum(days),0) FROM requests WHERE employee=?', (employee,)).fetchone()[0]
    return {'employee_id': employee, 'available_days': base - used}

def calendar(employee):
    record('employees.csv', employee)
    with connection() as db:
        result = db.execute('SELECT id,start,end,days FROM requests WHERE employee=? ORDER BY start', (employee,)).fetchall()
    return {'events': [dict(zip(['request_id','start','end','days'], r)) for r in result], 'source': 'mock calendar'}

def apply_leave(employee, request_id, start, end):
    count = days(start, end)
    if count == 0:
        raise ValueError('The range contains no working days')
    base = int(record('employees.csv', employee)['annual_leave_days'])
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT employee,start,end,days FROM requests WHERE id=?', (request_id,)).fetchone()
        if prior:
            if prior[:3] != (employee, start, end):
                raise ValueError('Request ID already used with different details')
            return {'request_id': request_id, 'days': prior[3], 'deduplicated': True}
        overlap = db.execute('SELECT 1 FROM requests WHERE employee=? AND start<=? AND end>=?', (employee,end,start)).fetchone()
        used = db.execute('SELECT coalesce(sum(days),0) FROM requests WHERE employee=?', (employee,)).fetchone()[0]
        if overlap or count > base - used:
            raise ValueError('Overlapping leave or insufficient balance')
        db.execute('INSERT INTO requests VALUES (?,?,?,?,?)', (request_id,employee,start,end,count))
    return {'request_id': request_id, 'days': count, 'deduplicated': False}
