"""Supervisor -> scoped specialist agents -> synthesis -> optional approval/write."""
from typing import TypedDict, Literal
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from .agent import build_agent, observations
from .tools import tools_for
from .answers import render
from .config import live, model
from .business import days, balance, apply_leave

class Plan(BaseModel):
    roles: list[Literal['policy_agent','records_agent']]

class WorkflowState(TypedDict, total=False):
    question: str
    employee: str
    request_id: str
    leave: dict | None
    plan: list[str]
    evidence: list[dict]
    answer: dict
    approved: bool

def build_workflow(checkpointer):
    def supervisor(state):
        if live():
            plan = model().with_structured_output(Plan).invoke([
                ('system', 'Choose specialists needed for this HR question. policy_agent searches policies; '
                 'records_agent reads balance, payroll and calendar. Select both for leave requests. '
                 'Use policy_agent for unsupported or unrelated questions. Return each role at most once.'),
                ('human', state['question'])]).roles
        else:
            q = state['question'].lower()
            plan = ['policy_agent']
            if any(x in q for x in ['balance','leave','payroll','calendar','salary','apply']):
                plan.append('records_agent')
        if state.get('leave'):
            plan = ['policy_agent', 'records_agent']
        return {'plan':list(dict.fromkeys(plan or ['policy_agent'])), 'evidence':[]}

    def specialist(role):
        def run(state):
            tools = tools_for(state['employee'], 3)
            tools = [t for t in tools if (t.name=='policy_search') == (role=='policy_agent')]
            agent = build_agent(tools)
            result = agent.invoke({'messages':[HumanMessage(content=state['question'])]}, {'recursion_limit':16})
            return {'evidence':state['evidence'] + observations(result['messages']), 'plan':state['plan'][1:]}
        return run

    def synthesis(state):
        answer = render(state['question'], state['evidence'])
        if state.get('leave'):
            count = days(**state['leave'])
            if count <= 0 or count > balance(state['employee'])['available_days']:
                answer.update(status='rejected', answer='No working days or insufficient leave balance.')
            else:
                answer.update(status='pending_approval', answer=f'{count} working days requested. Waiting for manager approval.')
        return {'answer':answer}

    def approval(state):
        decision = interrupt({'request_id':state['request_id'], 'employee_id':state['employee'],
                              'leave':state['leave'], 'working_days':days(**state['leave']),
                              'action':'Apply mock leave and update calendar'})
        if type(decision) is not bool:
            raise ValueError('Approval must be a JSON boolean')
        return {'approved':decision}

    def write(state):
        answer = dict(state['answer'])
        if not state['approved']:
            answer.update(status='rejected', answer='Manager rejected leave. No leave was recorded.')
        else:
            try:
                result = apply_leave(state['employee'], state['request_id'], **state['leave'])
                answer.update(status='applied', answer=f"Applied {result['days']} working days to the mock calendar.")
                answer['evidence'] = answer['evidence'] + [{'tool':'apply_leave','result':result}]
            except ValueError as exc:
                answer.update(status='rejected', answer=str(exc))
        return {'answer':answer}

    graph = StateGraph(WorkflowState)
    graph.add_node('supervisor', supervisor)
    for role in ('policy_agent','records_agent'):
        graph.add_node(role, specialist(role))
    graph.add_node('synthesis', synthesis)
    graph.add_node('approval', approval)
    graph.add_node('write', write)
    graph.add_edge(START,'supervisor')
    route = lambda s:s['plan'][0] if s['plan'] else 'synthesis'
    for node in ('supervisor','policy_agent','records_agent'):
        graph.add_conditional_edges(node, route)
    graph.add_conditional_edges('synthesis', lambda s:'approval' if s['answer']['status']=='pending_approval' else END)
    graph.add_edge('approval','write')
    graph.add_edge('write',END)
    return graph.compile(checkpointer=checkpointer)
