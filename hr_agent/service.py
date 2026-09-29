import sqlite3
import uuid
from threading import RLock
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langsmith import traceable
from .config import RUNTIME
from .schema import LeaveRequest
from .business import record
from .agent import build_agent, observations
from .answers import render
from .tools import tools_for
from .workflow import build_workflow

class Service:
    def __init__(self):
        self.db = sqlite3.connect(RUNTIME / 'checkpoints.sqlite', check_same_thread=False)
        self.checkpointer = SqliteSaver(self.db)
        self.workflow = build_workflow(self.checkpointer)
        # Single-process workshop server. Serializes new/resume races on thread state.
        self.lock = RLock()

    def config(self, employee, thread, hour):
        return {'configurable':{'thread_id':f'h{hour}:{employee}:{thread}'}, 'recursion_limit':32}

    @traceable(name='hr-request')
    def ask(self, employee, question, thread=None, hour=3, leave=None):
        record('employees.csv', employee)
        thread = thread or str(uuid.uuid4())
        config = self.config(employee, thread, hour)
        if leave:
            leave = LeaveRequest.model_validate(leave).model_dump(mode='json')
            if hour < 3:
                raise ValueError('Leave application is introduced in Hour 3')
        with self.lock:
            if hour < 3:
                graph = build_agent(tools_for(employee,hour), self.checkpointer if hour==2 else None)
                result = graph.invoke({'messages':[HumanMessage(content=question)]}, config)
                context = '\n'.join(str(m.content) for m in result['messages'] if m.type=='human')
                evidence = observations(result['messages'])
                return {'thread_id':thread, **render(context,evidence)}
            existing = self.workflow.get_state(config)
            if existing.next:
                raise ValueError('This thread has pending approval; resume it or use a new thread')
            result = self.workflow.invoke({'employee':employee,'question':question,'leave':leave,
                                          'request_id':str(uuid.uuid4())}, config)
            answer = {'thread_id':thread, **result['answer']}
            if result.get('__interrupt__'):
                answer['approval'] = result['__interrupt__'][0].value
            return answer

    @traceable(name='hr-manager-resume')
    def resume(self, employee, thread, approved):
        config = self.config(employee,thread,3)
        with self.lock:
            state = self.workflow.get_state(config)
            if not state.next:
                raise ValueError('No pending approval for this employee and thread')
            result = self.workflow.invoke(Command(resume=approved), config)
            return {'thread_id':thread, **result['answer']}
