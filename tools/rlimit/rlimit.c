/****************************************************************************
 *                                                                          *
 *                                RLIMIT.C                                  *
 *                                                                          *
 *                   Copyright (C) 1996-2017, AdaCore                       *
 *                                                                          *
 * This program is free software: you can redistribute it and/or modify     *
 * it under the terms of the GNU General Public License as published by     *
 * the Free Software Foundation, either version 3 of the License, or        *
 * (at your option) any later version.                                      *
 *                                                                          *
 * This program is distributed in the hope that it will be useful,          *
 * but WITHOUT ANY WARRANTY; without even the implied warranty of           *
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            *
 * GNU General Public License for more details.                             *
 *                                                                          *
 * You should have received a copy of the GNU General Public License        *
 * along with this program.  If not, see <http://www.gnu.org/licenses/>     *
 *                                                                          *
 ****************************************************************************/

/* rlimit - limit the execution time of a command

   Usage:
      rlimit seconds command [args]   */

#define _XOPEN_SOURCE 500 /* For setpgid */
#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>

void
usage (void)
{
  printf ("Usage:\n");
  printf ("   rlimit [--foreground] seconds command [args]\n");
  exit (1);
}

static int foreground = 0;
static int pid    = 0;
/* pid of child (controlled) process */

int status        = 0;
int return_status = 0;

/*
 * Handler for SIGTERM, also used for cleanup actions after receiving
 * SIGCHLD and SIGALRM.
 */

void
terminate_group(int nsig) {
  if (nsig != SIGCHLD) {
    /* Set SIGCHLD back to default */
    signal (SIGCHLD, SIG_DFL);
  }

  kill (-pid, SIGTERM);
  sleep (1);
  kill (-pid, SIGKILL);
}

/* Handler for SIGCHLD */

void
reapchild (int nsig)
{
  int delay;

  (void)nsig;

  if (pid > 0) {
    int rc;

    /*
     * Wait for the (only) child process. Since we have received SIGCHLD,
     * we know that this will not return ECHILD or 0. Note that waitpid(3)
     * won't report information for indirect descendants, but only for direct
     * child processes, in any case.
     */

    rc = waitpid (pid, &status, WNOHANG);
    if (rc < 0) {
       perror ("waitpid");
       return;
    }

    /* Get child process exit status */

    if (WIFEXITED (status) != 0) {
       return_status = WEXITSTATUS (status);
    } else {
       return_status = -125;
       /* ??? This junk value is invalid. */
    }

    /*
     * Check for remaining processes in the child group. Give them
     * 5 seconds to die gracefully.
     */

    delay = 5;
    while (delay > 0 && !(kill (-pid, 0) == -1 && errno == ESRCH)) {
      sleep (1);
      --delay;
    }

    if (delay == 0) {
       terminate_group (SIGCHLD);
    }

    /* Report exit status from child process to caller. */

    exit (return_status);

  } else {
    /* Never happens (the child process does an execve and does not fork). */
    exit (0);
  }
}

int
main (int argc, char **argv)
{
  int begin;
  sigset_t block_cld;

  /* we need at least 3 args */
  if (argc < 3)
    usage ();

  begin = 2;

  if (strcmp(argv[1], "--foreground") == 0) {
    ++foreground;
    ++begin;
  }
  else if (*argv[1] == '-')
      usage();

  /* argv[0] = .../rlimit
     argv[begin - 1] = seconds
     argv[begin] = command
     argv[begin + 1] = args */

  signal (SIGTERM, terminate_group);
  signal (SIGINT, terminate_group);

  /*
   * When the child process exits early, SIGCHLD might be emitted before the
   * pid variable is set in the parent process. On the other hand, we do want
   * to receive the signal so we have a chance to kill any other process it
   * might have spawned in the meantime. So, we establish the SIGCHLD handler
   * early, and block SIGCHLD until pid has been set.
   */

  signal (SIGCHLD, reapchild);

  sigemptyset(&block_cld);
  sigaddset(&block_cld, SIGCHLD);
  sigprocmask(SIG_BLOCK, &block_cld, NULL);

  /* In some cases rlimit might be launched with stdin and/or stdout being
   * a terminal. In that case at process startup, the rlimit process is
   * the foreground process group. This means that the following actions
   * will cause the child process to block:
   *     - read input from the terminal (SIGTTIN signal)
   *     - write output to the terminal
   *       (SIGTTOU signal if terminal mode TOSTOP enabled)
   *     - change terminal settings     (SIGTTOU signal)
   *
   * As rlimit is not supposed to read input the following is done:
   *
   * 1- make the child process the foreground process group
   * 2- allow the parent process to write in parallel to the terminal
   */

  pid = fork ();
  switch (pid) {
    case -1:
      perror ("fork");
      exit (3);

    case 0:
      /* first unblock SIGCHLD */
      sigprocmask(SIG_UNBLOCK, &block_cld, NULL);

      /* child exec the command in a new process group */
      if (setpgid (0, 0) == -1) {
        perror("setpgid");
        exit(4);
      }

      #if defined (__APPLE__)
        {
	  /* On this platform, if the RLIMIT_DYLD_ROOT_PATH environment
	     variable is defined, re-export it to the program being run
	     as DYLD_ROOT_PATH. This allows us to run program compiled
	     for the iOS simulator. We do this at the very last moment,
	     because this must not apply to rlimit itself (rlimit is not,
	     and cannot be, an iOS simulator application - creating new
	     processes are not allowed).  */
          const char *dyld_root_path = getenv ("RLIMIT_DYLD_ROOT_PATH");
          if (dyld_root_path != NULL)
            setenv ("DYLD_ROOT_PATH", dyld_root_path, 1);
        }
      #endif /* __APPLE__ */

      /* ignore SIGTTOU so that tcsetpgrp call does not block. */
      signal (SIGTTOU, SIG_IGN);

      /* If run with --foreground process group, rlimit must be able to
       * read and write from a tty (not only read => STDIN is a tty).
       *
       * If only stdout is a terminal there are no issues with not
       * being the foreground process as most terminals are configured
       * with TOSTOP off (so SIGTTOU is only emited in case of terminal
       * settings change.
       */
      if (foreground && tcsetpgrp(0, getpgid(getpid())) == -1) {
        perror("tcsetpgrp");
	    exit(4);
      }

      /* Restore SIGTTIN and SIGTTOU signal to their original value
       * in order not to impact children processes behaviour. */
      signal (SIGTTIN, SIG_DFL);

      /* When we are not in the foreground, we ignore SIGTTOU so that child process can
       * write. */
      if (foreground)
        signal (SIGTTOU, SIG_DFL);
      execvp ((const char *) argv[begin], (char *const *) &argv[begin]);
      fprintf (stderr, "rlimit: could not run \"%s\": ", argv[begin]);
      perror ("execvp");
      exit (5);

    default: {
      /* parent sleeps
         wake up when the sleep call returns or when
         SIGCHLD is received */
      int timeout = atoi (argv[begin - 1]);
      int seconds = timeout;

      /* At this stage rlimit might not be anymore the foreground process.
       * Ignore SIGTTOU in order to able to write and SIGTTIN for safety
       * (though no input is attempted from the rlimit itself).
       */
      signal (SIGTTOU, SIG_IGN);
      signal (SIGTTIN, SIG_IGN);

      /* pid variable is now set correctly so unblock SIGCHLD */
      sigprocmask(SIG_UNBLOCK, &block_cld, NULL);

      seconds = sleep (seconds);

      if (seconds == 0) {
        /* Sleep call returns, time limit elapsed, children must be slaughtered.
         *
         * Print the diagnostic first: On some systems (eg. LynxOS) the
         * handler for SIGCHLD may interrupt write(2) and garble the
         * message.
         */

        fprintf (stderr, "rlimit: Real time limit (%d s) exceeded\n", timeout);
        fflush (stderr);

        terminate_group (SIGALRM);
        exit (2);

      } else {
        /* sleep(3) was interrupted, assume it was a manual action. */
        exit (0);
      }
    }
  }
  return return_status;
}
