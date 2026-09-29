import os
import tempfile

# Tests never use the learner's data, real model keys, or tracing project.
os.environ['HR_RUNTIME'] = tempfile.mkdtemp(prefix='hr-workshop-test-')
os.environ['HR_MODE'] = 'demo'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ.setdefault('HR_EMPLOYEE_API_KEY','test-employee')
os.environ.setdefault('HR_MANAGER_API_KEY','test-manager')
