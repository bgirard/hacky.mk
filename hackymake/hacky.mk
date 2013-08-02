ifdef __WIN32__
ifndef .PYMAKE
$(error pymake is required to run hacky.mk on Windows.)
endif
endif

all:

include .hacky/*.hacky
include .hacky/*.hacky.pp

clobber:
	$(MAKE) -f Makefile
	hash FAILSOHARD!
