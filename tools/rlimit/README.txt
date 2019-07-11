rlimit - limit the execution time of a command
==============================================

There are two different implementation of the rlimit command,
one for windows rlimit-NT.c and one for UNIX platforms rlimit.c

To add a new platform, compile rlimit using:

$CC -o rlimit-$PLATFORM rlimit.c

or

$CC -o rlimit-$PLATFORM rlimit-NT.c

and copy the resulting binary into e3/os/data
