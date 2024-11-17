BFSS = """The rules of BFSS (Breadth-First Search Strategy) as outlined are:
	1.	Process One Level at a Time: Explore modules, classes, and functions one level deep before moving on to deeper levels. Modules are higher than classes. 
	2.	Directories are Higher-Level Entities: Treat directories as a higher level than individual modules or classes within those directories. 
	3.	Use Tools Appropriately for Each Level:
	•	inspect.getmembers: Use this to list members (classes, functions, etc.) of a given module or class at the current level.
	•	pyclbr: Useful for exploring classes and functions defined in a module without loading the module fully.
	•	pydoc.splitdoc: To split and format docstrings for better readability.
	•	os.path and pathlib: Useful for exploring directory structures and identifying modules at the filesystem level.
	4.	Confirmation at Each Level: After gathering information at a given level, filter out unwanted elements and confirm before proceeding deeper. Split each node into relevant, unrelevant, and 
AVOID:
	•	I may not have included all relevant signatures or detailed descriptions for each method.
	•	I might have missed certain elements or gone too deep without adhering to the specified depth restriction.
	•	There might have been a lack of organization or clarity in presenting the results, making it difficult to distinguish between classes, methods, and other elements."""
 

EXPLORE=BFSS
SYSTEM=f"""You can use the following system commands to navigate the filesystem:
  1.	ls: List directory contents.
  2.	cd: Change the current directory.
  3.	pwd: Print the current working directory.
  4.	mkdir: Create a new directory.
  5.	touch: Create a new file.
  6.	rm: Remove a file or directory.
  7.	mv: Move or rename a file or directory.
  8.	cp: Copy a file or directory.
  9.	cat: Display the contents of a file.
  10.	head: Display the first few lines of a file.
  11.	tail: Display the last few lines of a file.
  12.	grep: Search for a specific pattern in a file.
  13.	find: Search for files and directories in a directory hierarchy.
  14.	which: Locate a command.
  
You are a helpful assistant for performing research and gathering information before fullfilling tasks.
You have the following capabilities that can be used to assist you in your tasks. To use one, you must
respond in json format or a list of json formatted objects.

TOOLS:{TOOLS}"""