"""Identify issues.

2. Request every possible issue for the situation and a checklists of the issues.
3. Request the directed graph of dependencies between issues.
4. Run in parralel with topological sort.
5. Each subproblem--request the same with new subprompt and context.
6. Update the checklist when tests pass and manager approves.

Ex. 1: What are the issues with the code?
Ex. 2: Write a checklist of the issues.
Ex. 3: What are the dependencies between the issues? What can be done in parallel?
Ex. 4: Direct the assistants to solve the issues in parallel. Create a task group where each corutine is a multiprocess of the assistants solving and testing the issues in parallel. 
Ex. 5: Request the topological sort of the issues.
"""

PROMPT1= "What are the issues with the code?"
PROMPT2= "Write a checklist of the issues."
PROMPT3= "What are the dependencies between the issues? What can be done in parallel?"
PROMPT4= """Direct the assistants to solve the issues in parallel. Create a task group where each corutine is a multiprocess of the assistants solving and testing the issues in parallel. It is a topological sort through
the issues preventing the successful deployment of the code."""
PROMPT5= "."

