ifdef __WIN32__
ifndef .PYMAKE
$(error pymake is required to run hacky.mk on Windows.)
endif
endif

all:

include .hacky/*.mk
include .hacky/*.mk.pp

clobber:
	$(MAKE) -f Makefile
	hash FAILSOHARD!
