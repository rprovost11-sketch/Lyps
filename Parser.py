from abc import ABC, abstractmethod
from typing import Any, List, Tuple

class ScannerState( object ):
   def __init__( self ) -> None:
      self.tok: int             = 0
      self.buffer_source: str   = ''
      self.buffer_point: int    = 0
      self.buffer_mark: int     = 0
      self.buffer_lineNum: int  = 0

class ScannerBuffer( object ):
   def __init__( self ) -> None:
      '''Initialize a scanner buffer instance.'''
      self._source:str  = ''   # the string to be analyzed lexically
      self._point:int   = 0    # the current scanner position
      self._mark:int    = 0    # the first character of the lexeme currently being scanned
      self._lineNum:int = 1    # the current line number

   def reset( self, sourceString: str ) -> None:
      '''Re-initialize the instance over a new or the current string.'''
      self._source = sourceString
      self._point    = 0
      self._mark     = 0
      self._lineNum  = 1

   def peek( self ) -> str:
      '''Return the next character in the buffer.'''
      try:
         return self._source[ self._point ]        # raises on EOF
      except KeyError:
         return ''

   def consume( self ) -> None:
      '''Advance the point by one character in the buffer.'''
      try:
         if self._source[ self._point ] == '\n':   # raises on EOF
            self._lineNum += 1
         self._point += 1
      except KeyError:
         pass          # Scanned past eof

   def consumeIf( self, aCharSet: str ) -> None:
      '''Consume the next character if it's in aCharSet.'''
      try:
         if self._source[ self._point ] in aCharSet:   # raises on EOF
            self.consume( )
      except KeyError:
         pass          # Scanned past eof

   def consumeIfNot( self, aCharSet: str ) -> None:
      '''Consume the next character if it's NOT in aCharSet.'''
      try:
         if self._source[ self._point ] not in aCharSet:   # raises on EOF
            self.consume( )
      except KeyError:
         pass

   def consumePast( self, aCharSet: str ) -> None:
      '''Consume up to the first character NOT in aCharSet.'''
      try:
         while self._source[ self._point ] in aCharSet:   # raises on EOF
            self.consume( )
      except KeyError:
         pass

   def consumeUpTo( self, aCharSet: str ) -> None:
      '''Consume up to the first character in aCharSet.'''
      try:
         while self._source[ self._point ] not in aCharSet:   # raises on EOF
            self.consume( )
      except KeyError:
         pass

   def saveState( self, stateInst: ScannerState ) -> None:
      stateInst.buffer_source   = self._source
      stateInst.buffer_point    = self._point
      stateInst.buffer_mark     = self._mark
      stateInst.buffer_lineNum  = self._lineNum

   def restoreState( self, stateInst: ScannerState ) -> None:
      self._source   = stateInst.buffer_source
      self._point    = stateInst.buffer_point
      self._mark     = stateInst.buffer_mark
      self._lineNum  = stateInst.buffer_lineNum

   def markStartOfLexeme( self ) -> None:
      '''Indicate the start of a lexeme by setting the mark to the current vlaue of point.'''
      self._mark = self._point

   def getLexeme( self ) -> str:
      '''Returns the substring spanning from mark to point.'''
      return self._source[ self._mark : self._point ]

   def scanLineNum( self ) -> int:
      '''Return the line num (first line is 1) of point.'''
      return self._lineNum + 1

   def scanColNum( self ) -> int:
      '''Return the column numm (first column is 1) of point.'''
      return self._point - self._linePos( ) + 1

   def scanLineTxt( self ) -> str:
      '''Return the complete text of the line currently pointed to by point.'''
      fromIdx = self._linePos( )
      toIdx   = self._source.find( '\n', fromIdx )
      if toIdx == -1:
         return self._source[ fromIdx : ]
      else:
         return self._source[ fromIdx : toIdx ]

   def _linePos( self ) -> int:
      '''Return the index into the buffer string of the first character of the current line.'''
      return self._source.rfind( '\n', self._point ) + 1

class Scanner( ABC ):
   def __init__( self ) -> None:
      '''Initialize a Scanner instance.'''
      self.buffer:ScannerBuffer       = ScannerBuffer( )
      self._tok:int         = -1               # The next token

   def reset( self, sourceString: str ) -> None:
      '''Re-initialize the instance over a new or the current string.'''
      self.buffer.reset( sourceString )
      self._tok         = -1
      self.consume( )

   def peekToken( self ) -> int:
      '''Return the next (look ahead) token, but do not consume it.'''
      return self._tok

   def consume( self ) -> None:
      '''Advance the scanner to the next token/lexeme in the ScannerBuffer.'''
      self._tok = self._scanNextToken( )

   def getLexeme( self ) -> str:
      '''Return the next (look ahead) lexeme, but do not consume it.
      This should be called before consume.'''
      return self.buffer.getLexeme( )

   def saveState( self, stateInst: ScannerState ) -> None:
      '''Create a restore point (for backtracking).  The current
      state of the scanner is preserved under aStateName.'''
      stateInst.tok             = self._tok
      self.buffer.saveState( stateInst )

   def restoreState( self, stateInst: ScannerState ) -> None:
      '''Restore a saved state (backtrack to the point where the restore point was made).'''
      self._tok = stateInst.tok
      self.buffer.restoreState( stateInst )

   def tokenize( self, aString: str, EOFToken: int=0 ) -> List[Tuple[int, str]]:
      tokenList = [ ]

      self.reset( aString )

      while self.peekToken() != EOFToken:
         token = self.peekToken()
         lex   = self.getLexeme( )
         tokenList.append( ( token, lex ) )
         self.consume( )

      tokenList.append( (EOFToken,'') )

      return tokenList

   def test( self, aString: str, EOFToken: int=0 ) -> None:
      '''Scanner Testing:  Print the list of tokens in the input string.'''
      try:
         tokenList = self.tokenize( aString, EOFToken )

         for tokLexPair in tokenList:
            print( '{0:<4} /{1}/'.format( *tokLexPair ) )

      except ParseError as ex:
         print( ex )

      except Exception as ex:
         print( ex )

   @abstractmethod
   def _scanNextToken( self ) -> int:
      """Consume the next token (i.e. scan past it).
      Type:          Mutator - Abstract
      Returns:       Token (usually an int)
      Preconditions: determined by the implementation.
      Side Effects:  Scans the next token from the source string.
      """
      pass

class LineScanner( object ):
   def __init__( self, inputText: str ) -> None:
      self._lines:List[str] = inputText.splitlines(keepends=True)
      self._point:int = 0

   def peekLine( self ) -> str:
      try:
         return self._lines[ self._point ]
      except:
         raise StopIteration( )

   def consumeLine( self ) -> None:
      self._point += 1

   def currentLineNumber( self ) -> int:
      return self._point

class ParseError( Exception ):
   def __init__( self, aScanner: Scanner, errorMessage: str, filename: str='' ) -> None:
      self.filename:str   = filename
      self.lineNum:int    = aScanner.buffer.scanLineNum()
      self.colNum:int     = aScanner.buffer.scanColNum()
      self.errorMsg:str   = errorMessage
      self.sourceLine:str = aScanner.buffer.scanLineTxt()

      self.errInfo = {
         'filename':   self.filename,
         'lineNum':    self.lineNum,
         'colNum':     self.colNum,
         'errorMsg':   self.errorMsg,
         'sourceLine': self.sourceLine
         }

   def generateVerboseErrorString( self ):
      """Generate an error string.
      Category:      Pure Function.
      Returns:       (str) A detailed textual representation of the error.
      Side Effects:  None.
      Preconditions: [AssertionError] The underlying buffer must wrap a string.
      """
      self.errInfo['indentStr'] = ' ' * ( self.errInfo['colNum'] - 1 )
      return 'Syntax Error: {filename}({lineNum},{colNum})\n{sourceLine}\n{indentStr}^ {errorMsg}'.format( **self.errInfo )


class Parser( ABC ):
   @abstractmethod
   def parse( self, inputString: str ) -> Any:  # Returns an AST of inputString
      pass
