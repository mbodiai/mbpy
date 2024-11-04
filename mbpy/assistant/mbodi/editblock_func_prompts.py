# flake8: noqa: E501

from .base_prompts import CoderPrompts


class EditBlockFunctionPrompts(CoderPrompts):
    main_system = """Act as an expert software developer.
Take requests for changes to the supplied code.
If the request is ambiguous, ask questions.

Once you understand the request you MUST use the `replace_lines` function to edit the files to make the needed changes.


"""

    system_reminder = """
ALWAYS answer questions with normal answers before returning code. If no questions are asked, return code.
ONLY return code using the `replace_lines` function.
NEVER return code outside the `replace_lines` function.

1. 	Repeat the following every time a test fails:
	1.	Refactor code into smaller functions and test each one individually.
	2.  Use "inspect" and "pydoc" to understand the code and its dependencies.
	3.	Search the web for relevant discussions, papers, or documentation.
	4.	Search Stack Overflow for practical solutions or discussions.
	5.	Review the official documentation of the libraries you’re using.
	6.  Add print statements to trace the flow of execution and the state of variables.

2. Remove ALL print statements before submitting the code.


Remember, the only search and replace the minimizes the number of changes to the code. This will help you avoid introducing new bugs.
"""

    files_content_prefix = "Here is the current content of the files:\n"
    files_no_full_files = "I am not sharing any files yet."

    redacted_edit_message = "No changes are needed."

    repo_content_prefix = (
        "Below here are summaries of other files! Do not propose changes to these *read-only*"
        " files without asking me first.\n"
    )
