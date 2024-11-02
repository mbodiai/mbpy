import subprocess
from typing import List, Tuple

import pexpect


def execute_coq_script(script: str) -> Tuple[str, str, int]:
    # Run coqtop and pass the script as input
    process = subprocess.Popen(
        ["coqtop", "-batch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    output, error = process.communicate(input=script.encode("utf-8"))

    # Decode the output and error as strings
    output = output.decode("utf-8")
    error = error.decode("utf-8")

    # Check the return code of the process
    return_code = process.returncode
    return output, error, return_code


class Coqtop:
    """A Python interface to the Coq Proof Assistant using pexpect. We use the coqtop command line tool in emacs mode."""

    def __init__(self):
        """Initialize the Coqtop interface. This starts the Coqtop process in emacs mode."""
        # Check that coqtop is installed
        self.child = pexpect.spawn("coqtop -emacs", encoding="utf-8", timeout=10)   
        self._expect_prompt()

    def _expect_prompt(self) -> List[str]:
        """Private method that waits for the Coqtop prompt to appear."""
        return self.child.expect([r"</prompt>$", r"Error:", pexpect.TIMEOUT, pexpect.EOF])
      
        
        

    def send(self, command: str) -> Tuple[int, str, str]:
        """Send a command to Coqtop and return its response as a list of strings.

        Args:
            command (str): The command to be sent to Coqtop.

        Returns:
            List[str]: The output from Coqtop, split into lines.
        """
        self.child.sendline(command)
        return self._expect_prompt(), self.child.before, self.child.after

        


    def quit(self) -> None:
        """Quit the Coqtop process."""
        self.child.sendline("Quit.")
        self.child.expect(pexpect.EOF)
        self.child.close(force=True)

    def reset(self) -> None:
        """Reset the Coqtop session."""
        # Send the Reset command
        self.child.sendline("Reset Initial.")

        # Wait for the prompt
        self._expect_prompt()

    def __del__(self):
        """Destructor that ensures the Coqtop process is quit when the Coqtop object is garbage collected."""
        self.quit()
