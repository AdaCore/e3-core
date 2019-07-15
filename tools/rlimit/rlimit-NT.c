/****************************************************************************
 *                                                                          *
 *                             RLIMIT-NT.C                                  *
 *                                                                          *
 *                   Copyright (C) 1996-2014, AdaCore                       *
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

/* Define _WIN32_WINNT at least to 0x0500 in order to have visibility on Job
   related API.  */
#define _WIN32_WINNT  0x0500

#include <windows.h>
#include <stdio.h>
#include <winbase.h>

/* A few functions and constants are not defined in win32api */
#ifndef _W64
BOOL WINAPI SetInformationJobObject(
  HANDLE             hJob,
  JOBOBJECTINFOCLASS JobObjectInfoClass,
  LPVOID             lpJobObjectInfo,
  DWORD              cbJobObjectInfoLength
);
#else
#define JOB_OBJECT_BREAKAWAY_OK JOB_OBJECT_LIMIT_BREAKAWAY_OK
#endif

/* The following feature is only available starting with Windows XP. When the
   last handle on the job is closed the job is automatically terminated
   (i.e all processes that are part of the job are killed).  */
#define JOB_OBJECT_KILL_ON_JOB_CLOSE 0x00002000

void error_msg (char *msg) {
   fprintf (stderr, "rlimit: %s (error 0x%d)\n", msg, GetLastError ());
}

HANDLE create_job ()
{
  SECURITY_ATTRIBUTES                  JobAttributes;
  JOBOBJECT_BASIC_LIMIT_INFORMATION    JobBasicLimits;
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION JobExtendedLimits;
  HANDLE result;
  BOOL   status;

  /* We need to make sure that only the rlimit process holds a handler on
     the Job. This way, in case the rlimit process is killed, the associated
     Job and its processes will also be killed (JOB_OBJECT_KILL_ON_JOB_CLOSE
     is also set).  */
  JobAttributes.nLength = sizeof (SECURITY_ATTRIBUTES);
  JobAttributes.bInheritHandle = FALSE;
  JobAttributes.lpSecurityDescriptor = NULL;

  result = CreateJobObject (&JobAttributes, NULL);
  if (result == NULL)
  {
    error_msg ("cannot create new job");
    return NULL;
  }

  /* Set job attributes */
  JobBasicLimits.LimitFlags =
    JOB_OBJECT_BREAKAWAY_OK | JOB_OBJECT_KILL_ON_JOB_CLOSE;
  JobExtendedLimits.BasicLimitInformation = JobBasicLimits;

  status = SetInformationJobObject
    (result,
     JobObjectExtendedLimitInformation,
     &JobExtendedLimits,
     sizeof (JobExtendedLimits));
  if (status == 0) error_msg ("warning cannot set job attributes");

  return result;
}

usage ()
{
  printf ("Usage:\n");
  printf ("   rlimit [--daemon] [--no-job] seconds command [args]\n");
  printf ("   if WINDOWS_DESKTOP env var is set then a new desktop\n");
  printf ("   called WINDOWS_DESKTOP is created.\n");
  printf ("   --daemon: use rlimit as a daemon service\n");
  printf ("   --no-job: don't use windows jobs\n");
  exit (1);
}

main (int argc, char* argv[])
{
  /* Hold various Win32 API return status */
  BOOL result;

  /* Needed structures to spawn the subprocess */
  STARTUPINFO         StartupInfo;
  PROCESS_INFORMATION ProcessInfo;
  SECURITY_ATTRIBUTES ProcessAttr;
  HDESK               DesktopHandle;
  CHAR                DesktopName[32767];
  DWORD               DesktopNameSize;
  HANDLE              Job;
  DWORD               exit_code;
  int                 argv_pos = 1;
  char                CommandLine[4096];
  int                 Timeout;
  int                 use_jobs = 1;
  int                 daemon_mode = 0;
  int                 child_finished;

  /* We need at least 3 args.  */
  if (argc < 3)
    usage ();

  if (strcmp(argv[1], "--daemon") == 0)
  {
    daemon_mode = 1;
    argv_pos = 2;
  }

  if (strcmp(argv[argv_pos], "--no-job") == 0)
  {
    use_jobs = 0;
    argv_pos = argv_pos + 1;
  }

  /* Retrieve timeout and verify that it is positive */
  Timeout = atoi (argv[argv_pos]);
  if (Timeout < 0)
  {
    printf ("rlimit: timeout should be >= 0\n");
    exit (1);
  }
  if (Timeout == 0)
  {
    Timeout = INFINITE;
  } else
  {
    Timeout = 1000 * Timeout;
  }

  /* Compute command line string. When a parameter contains a " or a space we
     should quote it with doublequotes.  Double quotes inside the string should
     be escaped by a backslash.  All backslashes precedind a " should also be
     escaped.  */

  /* First copy the command name */
  strcpy (CommandLine, argv[argv_pos + 1]);
  strcat (CommandLine, " ");

  /* Now take care of the arguments */
  {
    int k;
    for (k = argv_pos + 2; k < argc; k++)
      {
        char *ca = argv[k]; /* current arg */
        int ca_index; /* index of the current character in ca */
        int need_quote = 1; /* set to 1 if quotes are needed */

        /* Should we quote the string ? */
        if (strlen(ca) > 0)
           need_quote = 0;

        for (ca_index = 0; ca_index < strlen(ca); ca_index++)
          {
            if (ca[ca_index] == ' ' || ca[ca_index] == '"')
              {
                need_quote = 1;
                break;
              }
          }

        /* Do quoting if necessary. Note it is important not to quote
           arguments that do not need it as some buggy implementations
           such vxsim will see for example -p as "-p" :-). */
        if (need_quote == 1)
          {
            int cl_index = strlen(CommandLine);

            /* Open the double quoted string */
            CommandLine[cl_index] = '"'; cl_index++;

            for (ca_index = 0; ca_index < strlen(ca); ca_index++)
              {

                /* We have a double in the argument. It should be escaped
                   along with all previous backslashes.  */
                if (ca[ca_index] == '"')
                  {
                    /* We have blackslashes before the double quote.
                       They should be quoted.  */
                    if (ca_index > 0 && ca[ca_index - 1] == '\\')
                      {
                        int j;
                        for (j = ca_index - 1; j >= 0 && ca[j] == '\\' ;j--)
                          {
                            CommandLine[cl_index] = '\\'; cl_index++;
                          }
                      }

                    CommandLine[cl_index] = '\\'; cl_index++;
                    CommandLine[cl_index] = '"';  cl_index++;
                  }
                else
                  {
                    /* This is not a double quote so just add the character */
                    CommandLine[cl_index] = ca[ca_index]; cl_index++;

                    /* We have blackslashes before the ending double quote.
                       They should be quoted.  */
                    if (ca[ca_index] == '\\' && ca_index + 1 == strlen(ca))
                      {
                        int j;
                        for (j = ca_index; j >= 0 && ca[j] == '\\' ;j--)
                          {
                            CommandLine[cl_index] = '\\'; cl_index++;
                          }
                      }
                  }
              }

            /* Close the doublequoted string */
            CommandLine[cl_index] = '"'; cl_index++;
            CommandLine[cl_index] = ' '; cl_index++;
            CommandLine[cl_index] = '\0';
          }
        else
          /* The argument does not need quoting. Just append it to the command
             line */
          {
            strcat (CommandLine, ca);
            strcat (CommandLine, " ");
          }
      }
  }

  while(1)
  {

    if (use_jobs == 1)
    {
       Job = create_job ();
       if (Job == NULL) exit (1);
    }

    /* Startup info */
    StartupInfo.cb          = sizeof (STARTUPINFO);
    StartupInfo.lpReserved  = NULL;
    StartupInfo.lpReserved2 = NULL;
    StartupInfo.lpDesktop   = NULL;
    StartupInfo.cbReserved2 = 0;
    StartupInfo.lpTitle     = NULL;
    StartupInfo.dwFlags     = 0;
    StartupInfo.wShowWindow = SW_HIDE;

    /* Security attributes */
    ProcessAttr.nLength              = sizeof (SECURITY_ATTRIBUTES);
    ProcessAttr.bInheritHandle       = TRUE;
    ProcessAttr.lpSecurityDescriptor = NULL;

    DesktopNameSize = GetEnvironmentVariable("WINDOWS_DESKTOP", DesktopName, 32767);
    if (DesktopNameSize > 0)
    {
       DesktopHandle = CreateDesktop (DesktopName, NULL, NULL, 0,
                                      DESKTOP_SWITCHDESKTOP|
                                      DESKTOP_WRITEOBJECTS|
                                      DESKTOP_READOBJECTS|
                                      DESKTOP_ENUMERATE|
                                      DESKTOP_CREATEWINDOW|
                                      DESKTOP_CREATEMENU,
              &ProcessAttr);
       StartupInfo.lpDesktop = DesktopName;
    }

    /* Spawn the process */
    result = CreateProcess
      (NULL,
       (char *) CommandLine,
       &ProcessAttr,          /* Process attributes */
       NULL,                  /* Thread attributes */
       TRUE,                  /* InheritHandles */
       NORMAL_PRIORITY_CLASS |
         CREATE_NEW_PROCESS_GROUP |
         CREATE_SUSPENDED |
         CREATE_BREAKAWAY_FROM_JOB , /* Creation flags */
       NULL,                  /* Environment */
       NULL,                  /* Current dir */
       &StartupInfo,          /* Startup info */
       &ProcessInfo);         /* Process Information */

    if (result == 0)
      {
        error_msg ("cannot spawn process");
        if (DesktopNameSize > 0) CloseDesktop(DesktopHandle);
        exit (1);
      }

    /* Assign the process to the Job */
    if (use_jobs == 1)
    {
      result = AssignProcessToJobObject (Job, ProcessInfo.hProcess);
    }

    /* Resume the child process */
    ResumeThread (ProcessInfo.hThread);

    /* Wait until child process terminates or until Timeout is reached.  */
    child_finished
      = WaitForSingleObject (ProcessInfo.hProcess, Timeout) == WAIT_OBJECT_0;

    if (child_finished)
    {

       /* Note that even if the spawned process has finished we want to be sure
          that all subprocesses are also terminated thus the call to
          TerminateJobObject. */
       if (!GetExitCodeProcess (ProcessInfo.hProcess, &exit_code))
       {
         exit_code = 0;
       }
    }

    /* Child process is not finished and timeout has elapsed so terminate the
       Job.  */
    if (use_jobs == 1) TerminateJobObject (Job, 1);
    if (DesktopNameSize > 0) CloseDesktop(DesktopHandle);
    CloseHandle (ProcessInfo.hProcess);

    if (!child_finished)
    {
      fprintf (stderr, "rlimit: Real time limit (%d s) exceeded\n", Timeout / 1000);
      exit_code = 2;
    }

    if (daemon_mode)
    {
      Sleep(1000);
      fprintf (stderr, "rlimit: prev status: %d, restart %s\n", exit_code, CommandLine);
    }
    else
    {
      exit(exit_code);
    }

  }
}
