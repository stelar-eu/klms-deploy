# This file is part of the STELAR distribution (https://github.com/stelar-eu).
# Copyright (c) 2023 Vasilis Samoladas.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
from typing import Union, Callable, List
import os
import pathlib


def goal(target: str, builder: Union[List[str], Callable]):
    """Execute a builder to generate a target in the tree.

    This function will first check if `target` exists. If not,
    it will execute the `builder` argument.

    The builder can be any of the following
    - an array of strings, which will be passed to `os.system` for
      execution, or
    - a callable, which will be called.

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
                if os.system(cmd) != 0:
                    break
    else:
        print(f"Target '{target}' exists")


if __name__ == '__main__':
    # Initialize tanka if it does not exist
    goal('jsonnetfile.json', [
        'jb init',
        'jb install github.com/jsonnet-libs/k8s-libsonnet/1.20@main',
    ])
