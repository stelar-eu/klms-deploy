
from typing import Union, Callable, List
import os
import pathlib

def goal(target: str, builder: Union[List[str],Callable]):
    """Execute a builder to generate a target in the tree.

    This function will first check if `target` exists. If not,
    it will execute the `builder` argument. 

    The B

    Args:
        target (str): the path to the resource examined.
        builder (Union[List[str],Callable]): the set of commands to execute
    """
    p = pathlib.Path(target)
    if not p.exists():
        print(f"Building {target}")
        if callable(builder):
            builder()
        else:
            for cmd in builder:
                print(f"    {cmd}")
                os.system(cmd)
    else:
        print(f"Target '{target}' exists")

if __name__ == '__main__':
    # Initialize tanka if it does not exist
    goal('vendor', ['tk init'])


