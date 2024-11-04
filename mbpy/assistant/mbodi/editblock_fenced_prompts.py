# flake8: noqa: E501

from .editblock_prompts import EditBlockPrompts


class EditBlockFencedPrompts(EditBlockPrompts):
    example_messages = [
        {
            "role": "user",
            "content": "Change get_factorial() to use math.factorial",
        },
        {
            "role": "assistant",
            "content": """To make this change we need to modify `mathweb/flask/app.py` to:



Before making changes, lets define the requirements and write pytest tests first.

1. Import the math package.
2. Remove the existing factorial() function.
3. Update get_factorial() to call math.factorial instead.

We'll start with the first step.

Here are the *SEARCH/REPLACE* blocks:

{fence[0]}
mathweb/flask/app.py
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
{fence[1]}

{fence[0]}
mathweb/flask/app.py
<<<<<<< SEARCH
def factorial(n):
    "compute factorial"

    if n == 0:
        return 1
    else:
        return n * factorial(n-1)

=======
>>>>>>> REPLACE
{fence[1]}

{fence[0]}
mathweb/flask/app.py
<<<<<<< SEARCH
    return str(factorial(n))
=======
    return str(math.factorial(n))
>>>>>>> REPLACE
{fence[1]}
<<<<<<< HEAD
""",
        },
        {
            "role": "user",
            "content": "Refactor hello() into its own file.",
        },
        {
            "role": "assistant",
            "content": """To make this change we need to modify `main.py` and make a new file `hello.py`:

1. Make a new hello.py file with hello() in it.
2. Remove hello() from main.py and replace it with an import.

Here are the *SEARCH/REPLACE* blocks:

{fence[0]}
hello.py
<<<<<<< SEARCH
=======
def hello():
    "print a greeting"

    print("hello")
>>>>>>> REPLACE
{fence[1]}

{fence[0]}
main.py
<<<<<<< SEARCH
def hello():
    "print a greeting"

    print("hello")
=======
from hello import hello
>>>>>>> REPLACE
{fence[1]}


REMEMBER: You ONLY suggest SEARCH/REPLCAE IF the user asks for implementations. First you 
    ask for which files to check and then you make a plan. Only THEN you suggest search/replace blocks.
""",
        },
    ]
