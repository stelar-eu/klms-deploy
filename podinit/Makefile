
.PHONY: all build push

CTRNAME = vsam/stelar-okeanos:podinit

all:
	@docker build . -t $(CTRNAME) --push

build:
	@docker build . -t $(CTRNAME)

push:
	@docker push $(CTRNAME)