import subprocess  

cpdef tuple run_command_c(command):  
    """Run a shell command using subprocess from Cython."""  
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)  
    stdout, stderr = process.communicate()  
    return (stdout, stderr, process.returncode)