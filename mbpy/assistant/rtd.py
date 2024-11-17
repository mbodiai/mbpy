from mbodied.agents.language import LanguageAgent


class Minimalist(LanguageAgent):
  def __init__(self, context=None):
    self.context = context
    
  def act(self, task, context):
    if len(self.history) > 10:
      self.forget()
    return super().act(task, context)
  
class Considerer(Minimalist):

    def act(self, task, context):
      prompt = f"""Is the answer or response to {task} immediately obvious in the context: {context}?
      
      If no, then should the task be broken down into smaller subtasks or should more information be gathered?
      """ + ""
      return super().act(prompt, context)

class Proprogator(Minimalist):
    def act(self, task, context) -> str:
        
        prompt = f"""What is the most relevant information in the context: {context} to {task}?
        
        Ensure that NO EXTRANEOUS information is included.
        """ + ""
        return super().act(prompt, context)
      
       
class Judger(Minimalist):
    def act(self, task, response, context) -> str:
      prompt = f"""Did the response {response} to the task {task} in the context {context} meet the requirements?
       
       If not, what was missing or incorrect?"""
      return super().act(prompt, context)
       
       

class Decomposer(Minimalist):
    def act(self, task, context) -> str:
        prompt = f"""What are the subtasks needed to complete the task {task} in the context {context}?
        
        Ensure that the subtasks are exhaustive and non-overlapping."""
        return super().act(prompt, context)
      
      
def main():
  from rich.prompt import Prompt
  from rich.protocol import Protocol