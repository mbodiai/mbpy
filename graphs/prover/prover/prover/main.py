from typing import Tuple

from rich.console import Console
from rich.panel import Panel


from prover.interact import Coqtop
from prover.agents import Checker, Prover

console = Console()
prover = Prover(
    goal="Prove the commutativity of addition for natural numbers.",
    model="gpt-4-0613",
)
checker = Checker(model="gpt-4-0613")
coqtop = Coqtop()


def check_coq(coq: str) -> Tuple[str, bool]:
    """Check if the coq proof is correct."""
    coqtop.reset()

    output = ""
    success = True
    # Execute the coq script line by line
    for line in coq.split("\n"):
        if line == "":
            continue
        # If the line starts with a coq comment,  skip it
        if line[0] == "(":
            continue

        # Execute the line
        idx, before, after = coqtop.send(line)

        # Print the result of executing the coq script in yellow
        output += str(before) + str(after) + "\n"

        console.print(Panel("> " + line + "\n" +  output, title="Coq Output", expand=True, style="yellow"))
        # Check for Error
        if "Error" in output:
            console.print(Panel(output, title="Coq Output", expand=True, style="red"))
            success = False
            break

    return output, success


feedback = None
accepted = False

while not accepted:
    # Take the first step in the proof
    natural, coq = prover.step(input=feedback)

    # Print the natural language output in blue
    console.print(Panel(natural, title="Natural Language Output", expand=True, style="blue"))

    # Print the coq output in red
    console.print(Panel(coq, title="Coq Output", expand=True, style="red"))

    coq_output, coq_success = check_coq(coq)

    if not coq_success:
        feedback = f"Coq error: {coq_output}\n Check your proof for corectness, check the Coq code for syntax errors, and try again."
    else:
        # Print the feedback in green
        feedback, accepted = checker.check(natural)
        console.print(Panel(feedback, title="Feedback", expand=True, style="green"))
        if accepted:
            break