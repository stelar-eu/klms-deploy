#! /bin/bash
exec kubectl run ontop-cmd --image=vsam/stelar-okeanos:ontop --rm -it --restart=Never -- "$@"
