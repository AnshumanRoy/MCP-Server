from . import answer, explore


def register_all(mcp) -> None:
    explore.register(mcp)
    answer.register(mcp)
