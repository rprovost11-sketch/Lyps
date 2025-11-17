import ltk_py3.Parser as Parser
import sys
import datetime
import time
from abc import ABC, abstractmethod
from typing import List, Tuple, Any

class Interpreter( ABC ):
   '''Interpreter interface used by Listener.
   To use the Listener class, the execution environment must be encapsulated
   behind the following interface.
   '''
   @abstractmethod
   def reboot( self ):
      '''Reboot the interpreter.'''
      pass

   @abstractmethod
   def eval( self, anExprStr: str ):
      '''Evaluate an expression string of the target language and return a
      string expr representing the result of the evaluation.

      Currently, Listener only understands how to deal with eval() that returns
      strings.  Future incarnations of Listener may recognize other return value
      types.

      The caller can supply streams to use in place of stdin, stdout and stderr.

      EXCEPTIONS:
         Implementation should bundle errors and exceptions such that only
         two kinds of exceptions leave
      '''
      pass

   @abstractmethod
   def runtimeLibraries( self ):
      '''Returns a list of filenames which are the Lyps intepreter runtime
      libraries.
      '''
      pass

   @abstractmethod
   def testFileList( self ):
      '''Returns a list of filenames which are the Lyps intepreter tests.
      '''
      pass


class Listener( object ):
   '''A generic Listener environment for dynamic languages.
   Heavily ripped-off from Python's own cmd library.'''
   prompt0 = '>>> '
   prompt1 = '... '
   nohelp = "*** No help on %s"
   ruler = '='
   doc_leader = ""
   doc_header = "Documented commands (type help <topic>):"

   def __init__( self, anInterpreter: Interpreter, **keys ) -> None:
      super().__init__( )

      self._interp     = anInterpreter
      self._logFile: Any   = None
      self._exceptInfo: Any = None
      self.writeLn( '{language:s} {version:s}'.format(**keys) )
      self.writeLn( '- Execution environment initialized.' )
      self.do_reboot( [ ] )

   def writeLn( self, value: str='' ) -> None:
      print( value )
      if self._logFile:
         self._logFile.write( value + '\n' )

   def prompt( self, prompt: str='' ) -> str:
      inputStr: str = input( prompt ).lstrip()
      if self._logFile and ((len(inputStr) == 0) or (inputStr[0] != ']')):
         self._logFile.write( f'{prompt}{inputStr}\n' )

      return inputStr.strip( )

   def do_reboot( self, args: List[str] ) -> None:
      '''Usage: reboot
      Reset the interpreter.
      '''
      if len(args) > 0:
         print( self.do_reboot.__doc__ )
         return

      if self._logFile:
         print( 'Please close the log before exiting.' )
         return

      self._interp.reboot( )
      print( '- Runtime environment reinitialized.' )

      for libFileName in self._interp.runtimeLibraries():
         self.readAndEvalFile( libFileName )
      print( '- Runtime libraries loaded.' )
      print( 'Listener started.' )
      print( 'Enter any expression to have it evaluated by the interpreter.')
      print( 'Enter \']help\' for listener commands.' )
      print( 'Welcome!' )

   def do_log( self, args: List[str] ) -> None:
      '''Usage:  log <filename>
      Begin a new logging session.
      '''
      if len(args) != 1:
         print( self.do_log.__doc__ )
         return

      filename = args[0]
      if self._logFile is not None:
         print( 'Already logging.\n' )
         return

      try:
         self._logFile = open( filename, 'w' )
      except OSError:
         print( 'Unable to open file for writing.' )
         return

      self.writeLn( '>>> ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;' )
      self.writeLn( '... ;;;;;;  Starting Log ( {0} ): {1}'.format( datetime.datetime.now().isoformat(), filename ) )
      self.writeLn( '... 0')
      self.writeLn( '' )
      self.writeLn( '==> 0')

   def do_read( self, args: List[str] ) -> None:
      '''Usage:  read <filename> [v|v]
      Read and execute a log file.  V is for verbose.
      '''
      if len(args) not in ( 1, 2 ):
         print( self.do_read.__doc__ )
         return

      verbosity: int=0
      if len(args) == 2:
         if args[1].upper() == 'V':
            verbosity=3

      filename: str = args[0]
      self.readAndEvalFile( filename, testFile=False, verbosity=verbosity )
      print( f'Log file read successfully: {filename}' )

   def do_test( self, args: List[str] ) -> None:
      '''Usage:  test <filename>
      Test the interpreter using a log file.
      Read and execute a log file;
      comparing the return value to the log file return value.
      '''
      numArgs = len(args)
      if numArgs not in ( 0, 1 ):
         print( self.do_test.__doc__ )
         return

      if numArgs == 1:
         filename = args[0]
         filenameList = [ filename ]
      else:
         filenameList = self._interp.testFileList( )

      for filename in filenameList:
         self.readAndEvalFile( filename, testFile=True, verbosity=3 )

   def do_continue( self, args: List[str] ) -> None:
      '''Usage:  continue <filename> [V|v]
      Read and execute a log file.  Keep the log file open to
      continue a logging session where you left off.  V reads
      the file verbosely.
      '''
      if self._logFile:
         print( "A log file is already open and logging.  If you wish to log in a different" )
         print( "file, you must first close the current logging session." )
         return

      numArgs = len(args)
      if numArgs not in ( 1, 2 ):
         print( self.do_continue.__doc__ )
         return

      self.do_read( args )

      filename = args[0]
      try:
         self._logFile = open( filename, 'a' )
      except OSError:
         print( 'Unable to open file for append.' )
         return

      self.writeLn( '>>> ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;' )
      self.writeLn( '... ;;;;;;  Continuing Log ( {0} ): {1}'.format( datetime.datetime.now().isoformat(), filename ) )
      self.writeLn( '... 0')
      self.writeLn( '' )
      self.writeLn( '==> 0')

   def do_close( self, args: List[str] ) -> None:
      '''Usage:  close
      Close the current logging session.
      '''
      if len(args) != 0:
         print( self.do_close.__doc__ )
         return

      if self._logFile is None:
         print( "Not currently logging." )
         return

      self.writeLn( '>>> ;;;;;;  Logging ended.' )
      self.writeLn( '... ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;' )
      self.writeLn( '... 0')
      self.writeLn( '' )
      self.writeLn( '==> 0')

      self._logFile.close( )

      self._logFile = None

   def do_dump( self, args: List[str] ) -> None:
      '''Usage:  dump
      Dump a stack trace of the most recent error.
      '''
      if len(args) != 0:
         print( self.do_dump.__doc__ )
         return

      if self._exceptInfo is None:
         self.writeLn( 'No exception information available.\n' )
         return

      sys.excepthook( *self._exceptInfo )

   def do_exit( self, args: List[str] ) -> None:
      '''Usage:  exit
      Exit the interpreter and listener.
      '''
      if self._logFile is not None:
         print( "Logging must be stopped before you can exit." )
         return

      if len(args) != 0:
         print( self.do_exit.__doc__ )
         return

      self.writeLn( 'Bye.' )
      raise Exception( )

   def do_help(self, args: List[str] ) -> None:
      '''Usage: help [<command>]
      List all available commands, or detailed help for a specific command.
      '''
      if len(args) > 0:
         arg = args[0]
         # XXX check arg syntax
         try:
            doc=getattr(self, f'do_{arg}').__doc__
            if doc:
               print(str(doc))
               return
         except AttributeError:
            pass
         print(str(self.nohelp % (arg,)))
         return
      else:
         names = dir(self.__class__)
         names.sort()
         cmds_doc = []
         # There can be duplicates if routines overridden
         prevname = ''
         for name in names:
            if name[:3] == 'do_':
               if name == prevname:
                  continue
               prevname = name
               cmd=name[3:]
               cmds_doc.append(cmd)
         print(self.doc_leader)
         self.print_topics( cmds_doc, 15, 80 )

   def print_topics( self, cmds: List[str], cmdlen: int, maxcol: int ) -> None:
      if cmds:
         print(str(self.doc_header))
         if self.ruler:
            print(str(self.ruler * len(self.doc_header)))
         self.columnize(cmds, maxcol-1)
         print()

   def columnize(self, list, displaywidth: int=80) -> None:
      """Display a list of strings as a compact set of columns.

      Each column is only as wide as necessary.
      Columns are separated by two spaces (one was not legible enough).
      """
      if not list:
         print("<empty>")
         return

      nonstrings = [i for i in range(len(list))
                    if not isinstance(list[i], str)]
      if nonstrings:
         raise TypeError("list[i] not a string for i in %s"
                         % ", ".join(map(str, nonstrings)))
      size = len(list)
      if size == 1:
         print(str(list[0]))
         return
      # Try every row count from 1 upwards
      for nrows in range(1, len(list)):
         ncols = (size+nrows-1) // nrows
         colwidths = []
         totwidth = -2
         for col in range(ncols):
            colwidth = 0
            for row in range(nrows):
               i = row + nrows*col
               if i >= size:
                  break
               x = list[i]
               colwidth = max(colwidth, len(x))
            colwidths.append(colwidth)
            totwidth += colwidth + 2
            if totwidth > displaywidth:
               break
         if totwidth <= displaywidth:
            break
      else:
         nrows = len(list)
         ncols = 1
         colwidths = [0]
      for row in range(nrows):
         texts = []
         for col in range(ncols):
            i = row + nrows*col
            if i >= size:
               x = ""
            else:
               x = list[i]
            texts.append(x)
         while texts and not texts[-1]:
            del texts[-1]
         for col in range(len(texts)):
            texts[col] = texts[col].ljust(colwidths[col])
         print(str("  ".join(texts)))

   def doCommand( self, listenerCommand: str ) -> None:
      cmdParts  = listenerCommand[1:].split( ' ' )
      cmd,*args = cmdParts

      try:
         func = getattr(self, f'do_{cmd}')
         func(args)
      except AttributeError:
         print( f'Unknown command "{listenerCommand}"' )

   def readEvalPrintLoop( self ) -> None:
      inputExprLineList: List[str] = [ ]

      while True:
         if len(inputExprLineList) == 0:
            lineInput = self.prompt( '>>> ' ).strip()
         else:
            lineInput = self.prompt( '... ' ).strip()

         if (lineInput == '') and (len(inputExprLineList) != 0):
            inputExprStr = ''.join( inputExprLineList )
            if inputExprStr[0] == ']':
               self.doCommand( inputExprStr[:-1] )
            else:
               try:
                  start = time.perf_counter( )
                  resultStr = self._interp.eval( inputExprStr )
                  cost  = time.perf_counter( ) - start
                  self.writeLn( f'\n==> {resultStr}' )
                  print( f'-------------  Total execution time:  {cost:15.5f} sec' )

               except Parser.ParseError as ex:
                  self._exceptInfo = sys.exc_info( )
                  self.writeLn( ex.generateVerboseErrorString() )

               except Exception as ex:
                  self._exceptInfo = sys.exc_info( )
                  self.writeLn( ex.args[-1] )

               self.writeLn( )

            inputExprLineList = [ ]

         else:
            inputExprLineList.append( lineInput + '\n' )

   def readAndEvalFile( self, filename: str, testFile: bool=False, verbosity: int=0 ) -> None:
      inputText = None
      with open( filename, 'r') as file:
         inputText = file.read( )

      if inputText is None:
         self.writeLn( 'Unable to read file.\n' )
         return

      if testFile:
         print( f'   Test file: {filename}... ', end='' )
         self._sessionLog_test( inputText, verbosity=3 )
      else:
         self._sessionLog_restore( inputText, verbosity )

   def _sessionLog_restore( self, inputText: str, verbosity: int=0 ) -> None:
      for exprNum,exprPackage in enumerate(self.parseLog(inputText)):
         exprStr,outputStr,retValStr = exprPackage
         if verbosity == 0:
            self._interp.eval( exprStr )
         else:
            exprLines = exprStr.splitlines()
            for lineNum, line in enumerate(exprLines):
               if lineNum == 0:
                  print( f'\n>>> {line}' )
               else:
                  print( f'... {line}')

            resultStr = self._interp.eval( exprStr )
            print( f'\n==> {resultStr}' )

   def _sessionLog_test( self, inputText: str, verbosity: int=0 ) -> None:
      numPassed = 0

      if verbosity >= 3:
         print()

      for exprNum,exprPackage in enumerate(self.parseLog(inputText)):
         exprStr,expectedOutput,expectedRetValStr = exprPackage
         actualRetValStr = self._interp.eval( exprStr )

         # Test Return Value
         if (actualRetValStr is None) and (expectedRetValStr is not None):
            retValTest_reason = 'Failed!  Returned <Code>None</Code>; expected <i>value</i>.'
         elif (actualRetValStr is not None) and (expectedRetValStr is None):
            retValTest_reason = 'Failed!  Returned a value; expected <Code>None</Code>'
         elif (actualRetValStr is not None) and (expectedRetValStr is not None):
            if actualRetValStr == expectedRetValStr:
               retValTest_reason = 'PASSED!'
               numPassed += 1
            else:
               retValTest_reason = 'Failed!  Return value doesn\'t equal expected value.'

         if verbosity >= 3:
            print( f'     {str(exprNum).rjust(6)}. {retValTest_reason}' )

      numTests = exprNum + 1
      numFailed = numTests - numPassed
      if numFailed == 0:
         print( 'ALL PASSED!' )
      else:
         print( f'({numFailed}/{numTests}) Failed.' )

   def parseLog( self, inputText: str ) -> List[Tuple[str, str, str]]:
      stream = Parser.LineScanner( inputText )
      parsedLog = [ ]
      eof = False

      while not eof:
         expr = ''
         output = ''
         retVal = ''

         # Skip to the begenning of an interaction prompt
         try:
            line = stream.peekLine()
            while not line.startswith( '>>> ' ):
               stream.consumeLine()
               line = stream.peekLine()

            # Parse Expression
            # string variable *line* begins with '>>> '
            expr = line[ 4: ]
            stream.consumeLine()
            line = stream.peekLine()
            while not eof and line.startswith( '... ' ):
               expr += line[ 4: ]
               stream.consumeLine()
               line = stream.peekLine()

            # Parse Output from the evaluation (such as write statements)
            while not line.startswith( ('==> ','... ','>>> ') ):
               # Parse written output
               if output is None:
                  output = ''
               output += line
               stream.consumeLine()
               line = stream.peekLine()

            # Parse Return Value
            if line.startswith( '==> ' ):
               retVal = line[ 4: ]
               stream.consumeLine()
               line = stream.peekLine()
               while not eof and not line.startswith( ('==> ','... ','>>> ', ';') ):
                  retVal += line
                  stream.consumeLine()
                  line = stream.peekLine()

         except StopIteration:
            eof = True

         parsedLog.append( (expr,output.rstrip(),retVal.rstrip()))

      return parsedLog


