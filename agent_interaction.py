import asyncio
from graphs.prover.prover.prover.agents import Prover, Checker
from rich.console import Console

console = Console()

async def agent_interaction():
    # Initialize the prover and checker agents
    prover = Prover(goal="Prove that the sum of two even numbers is even.")
    checker = Checker()

    # Prover generates a proof
    console.print("Prover Agent is generating a proof...")
    natural, coq = prover.step(None)
    console.print("Generated Proof (Natural Language):", natural)
    console.print("Generated Proof (Coq):", coq)

    # Checker evaluates the proof
    console.print("Checker Agent is evaluating the proof...")
    feedback, accepted = checker.check(natural)
    console.print("Feedback:", feedback)
    console.print("Accepted:", accepted)

if __name__ == "__main__":
    asyncio.run(agent_interaction())
