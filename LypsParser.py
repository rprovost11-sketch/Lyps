import ltk_py3.Parser as Parser
from LypsAST import LList, LSymbol
import fractions
from typing import List, Any

"""
The Language
------------
Lexemes
   Comments
      Comments extend from ';;' through '\n'.
      All text between and including these two delimiters is ignored.

   Delimiters:
      ';', '#', '(', ')', '|', '[', ']', ';;', '\n'

   Literals
      NumberLiteral:  ['+'|'-'] ('0' .. '9')+
                         ( '/' ('0' .. '9' )+
                         | 'e' ['+'|'-'] ('0' .. '9')+
                         | '.' ('0' .. '9')+ [ 'e' ['+'|'-'] ('0' .. '9')+ ]
                         )
      StringLiteral:  '"' (^('"'))* '"'
      Symbol:         'a..zA..Z+-~!$%^&*_=\:/?<>'
                      { 'a..zA..Z+-~!$%^&*_=\:/?<>0..9' }

   Reserved Symbols
         'null', 'e', 'pi', 'inf', 'nan'

Grammar
   Start:
      Object EOF

   Object:
      NumberLiteral | StringLiteral | Symbol | List | '#' | '|' | ':' | '[' | ']'
      | "'" Object | "`" Object | "," Object | ",@" Object

   List:
      '(' Object* ')'
"""

class LypsScanner( Parser.Scanner ):
   WHITESPACE     = ' \t\n\r'
   SIGN           = '+-'
   DIGIT          = '0123456789'
   SIGN_OR_DIGIT  = SIGN + DIGIT
   ALPHA_LOWER    = 'abcdefghijklmnopqrstuvwxyz'
   ALPHA_UPPER    = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
   ALPHA          = ALPHA_LOWER + ALPHA_UPPER
   SYMBOL_OTHER   = '~!$%^&*_=\/?<>'
   SYMBOL_FIRST   = ALPHA + SIGN + SYMBOL_OTHER
   SYMBOL_REST    = ALPHA + SIGN + SYMBOL_OTHER + DIGIT + ':'

   EOF_TOK            =   0

   SYMBOL_TOK         = 101    # Value Objects
   STRING_TOK         = 102
   INTEGER_TOK        = 111
   FLOAT_TOK          = 112
   FRAC_TOK           = 121

   OPEN_BRACKET_TOK   = 201    # Paired Symbols
   CLOSE_BRACKET_TOK  = 202
   OPEN_PAREN_TOK     = 211
   CLOSE_PAREN_TOK    = 212

   SEMI_COLON_TOK     = 500    # Other Symbols
   POUND_SIGN_TOK     = 501
   PIPE_TOK           = 502
   COLON_TOK          = 503
   SINGLE_QUOTE_TOK   = 504
   COMMA_TOK = 505
   COMMA_AT_TOK = 506
   BACK_QUOTE_TOK = 507

   def __init__( self, ) -> None:
      super( ).__init__( )

   def _scanNextToken( self ) -> int:
      buf = self.buffer

      try:
         self._skipWhitespaceAndComments( )

         nextChar = buf.peek( )
         if nextChar is None:
            return LypsScanner.EOF_TOK
         elif nextChar == '[':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.OPEN_BRACKET_TOK
         elif nextChar == ']':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.CLOSE_BRACKET_TOK
         elif nextChar == '(':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.OPEN_PAREN_TOK
         elif nextChar == ')':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.CLOSE_PAREN_TOK
         elif nextChar == ';':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.SEMI_COLON_TOK
         elif nextChar == '#':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.POUND_SIGN_TOK
         elif nextChar == '|':
            buf.markStartOfLexeme( )
            buf.consume( )
            return LypsScanner.PIPE_TOK
         elif nextChar == ':':
            buf.markStartOfLexeme( )
            buf.consume( )
            nextChar = buf.peek( )
            return LypsScanner.COLON_TOK
         elif nextChar == "'":
            buf.markStartOfLexeme( )
            buf.consume( )
            nextChar = buf.peek( )
            return LypsScanner.SINGLE_QUOTE_TOK
         elif nextChar == '`':
            buf.markStartOfLexeme( )
            buf.consume( )
            nextChar = buf.peek( )
            return LypsScanner.BACK_QUOTE_TOK
         elif nextChar == ',':
            buf.markStartOfLexeme( )
            buf.consume( )
            nextChar = buf.peek( )
            if nextChar == '@':
               buf.consume( )
               nextChar = buf.peek( )
               return LypsScanner.COMMA_AT_TOK
            else:
               return LypsScanner.COMMA_TOK
         elif nextChar == '"':
            return self._scanStringLiteral( )
         elif nextChar in LypsScanner.SIGN_OR_DIGIT:
            return self._scanNumOrSymbol( )
         elif nextChar in LypsScanner.SYMBOL_FIRST:
            return self._scanSymbol( )
         else:
            raise Parser.ParseError( self, 'Unknown Token' )

      except Parser.ParseError:
         raise

      except:
         return LypsScanner.EOF_TOK

   def _scanStringLiteral( self ) -> int:
      buf = self.buffer

      nextChar = buf.peek( )
      if nextChar != '"':
         raise Parser.ParseError( self, '\'"\' expected.' )
      buf.markStartOfLexeme( )
      buf.consume( )
      buf.consumeUpTo( '"' )
      buf.consume( )

      return LypsScanner.STRING_TOK

   def _scanNumOrSymbol( self ) -> int:
      '''
      NumberLiteral:  ['+'|'-']('0' .. '9')+                                    # <-- leader
                         ( '/' ('0' .. '9')+                                    # <-- fraction case
                         | 'e' ['+'|'-'] ('0' .. '9')+                          # <-- exponentiation case
                         | '.' ('0' .. '9')+ [ 'e' ['+'|'-'] ('0' .. '9')+ ]    # <-- decimal/exponentiation case
                         )
      '''
      buf = self.buffer

      SAVE = Parser.ScannerState( )
      nextChar = buf.peek( )

      buf.markStartOfLexeme( )
      self.saveState( SAVE )                  # Save the scanner state

      buf.consume( )

      if nextChar in LypsScanner.SIGN:
         secondChar = buf.peek( )
         if (secondChar is None) or (secondChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )         # Restore the scanner state
            return self._scanSymbol( )

      buf.consumePast( LypsScanner.DIGIT )
      nextChar = buf.peek()

      if nextChar == '/':
         # Possibly a Fraction number
         buf.consume( )

         nextChar = buf.peek( )
         if (nextChar is None) or (nextChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )         # Restore the scanner state
            return self._scanSymbol( )

         buf.consumePast( LypsScanner.DIGIT )
         return LypsScanner.FRAC_TOK

      elif nextChar in ('e', 'E'):
         # Exponentiation case
         buf.consume( )

         nextChar = buf.peek( )
         if (nextChar not in LypsScanner.SIGN) and (nextChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )
            return self._scanSymbol( )

         if nextChar in LypsScanner.SIGN:
            buf.consume( )
            nextChar = buf.peek( )

         if (nextChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )
            return self._scanSymbol( )

         buf.consumePast( LypsScanner.DIGIT )
         return LypsScanner.FLOAT_TOK

      elif nextChar == '.':
         # Possibly a floating point number
         # '.' ('0' .. '9')+ [ 'e' ['+'|'-'] ('0' .. '9')+ ]    # <-- decimal/exponentiation case
         #self.saveState( SAVE )
         buf.consume()
         nextChar = buf.peek()
         if nextChar not in LypsScanner.DIGIT:
            # Integer
            self.restoreState( SAVE )
            return self._scanSymbol( )

         buf.consumePast( LypsScanner.DIGIT )
         nextChar = buf.peek( )

         if nextChar not in ('e', 'E'):
            return LypsScanner.FLOAT_TOK

         buf.consume( )
         nextChar = buf.peek( )

         if (nextChar not in LypsScanner.SIGN) and (nextChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )
            return self._scanSymbol( )

         if nextChar in LypsScanner.SIGN:
            buf.consume( )
            nextChar = buf.peek( )

         if (nextChar not in LypsScanner.DIGIT):
            self.restoreState( SAVE )
            return self._scanSymbol( )

         buf.consumePast( LypsScanner.DIGIT )
         return LypsScanner.FLOAT_TOK

      return LypsScanner.INTEGER_TOK

   def _scanSymbol( self ) -> int:
      buf = self.buffer

      buf.markStartOfLexeme( )
      nextChar = buf.peek()
      if nextChar not in LypsScanner.SYMBOL_FIRST:
         raise Parser.ParseError( self, 'Invalid symbol character' )
      buf.consume( )

      buf.consumePast( LypsScanner.SYMBOL_REST )

      return LypsScanner.SYMBOL_TOK

   def _skipWhitespaceAndComments( self ) -> None:
      buf = self.buffer

      SAVE = Parser.ScannerState( )

      while buf.peek() in '; \t\n\r':
         buf.consumePast( ' \t\n\r' )

         if buf.peek() == ';':
            self.saveState( SAVE )
            buf.consume()
            if buf.peek() == ';':
               buf.consumeUpTo( '\n\r' )
            else:
               self.restoreState( SAVE )
               return


class LypsParser( Parser.Parser ):
   def __init__( self ) -> None:
      self._scanner    = LypsScanner( )

   def parse( self, inputString: str ) -> Any:  # Returns an AST of inputString
      self._scanner.reset( inputString )

      syntaxTree = self._parseObject( )

      # EOF
      if self._scanner.peekToken( ) != LypsScanner.EOF_TOK:
         raise Parser.ParseError( self._scanner, 'EOF Expected.' )

      self._scanner.consume( )

      return syntaxTree

   def _parseObject( self ) -> Any: # Returns an AST or None if eof
      nextToken = self._scanner.peekToken( )
      lex: str = ''           # Holds the lexeme string
      lexVal: Any = None      # Holds the parsed AST

      if nextToken == LypsScanner.INTEGER_TOK:
         lex = self._scanner.getLexeme( )
         lexVal = int(lex)
         self._scanner.consume( )
      elif nextToken== LypsScanner.FLOAT_TOK:
         lex = self._scanner.getLexeme( )
         lexVal = float(lex)
         self._scanner.consume( )
      elif nextToken== LypsScanner.FRAC_TOK:
         lex = self._scanner.getLexeme( )
         lex_num,lex_denom = lex.split('/')
         lexVal    = fractions.Fraction( int(lex_num),
                                         int(lex_denom) )
         self._scanner.consume( )
      elif nextToken == LypsScanner.STRING_TOK:
         lex = self._scanner.getLexeme( )
         lexVal = lex[1:-1]
         self._scanner.consume( )
      elif nextToken == LypsScanner.SYMBOL_TOK:
         lex = self._scanner.getLexeme( ).upper( )   # Make symbols case insensative
         lexVal = LSymbol(lex)
         self._scanner.consume( )
      elif nextToken == LypsScanner.OPEN_PAREN_TOK:
         lex = '()'
         lexVal = self._parseList( )
      elif nextToken == LypsScanner.SINGLE_QUOTE_TOK:
         lex = self._scanner.getLexeme( )
         self._scanner.consume( )
         subordinate = self._parseObject( )
         lexVal = LList( LSymbol('QUOTE'), subordinate )
      elif nextToken == LypsScanner.BACK_QUOTE_TOK:
         lex = self._scanner.getLexeme( )
         self._scanner.consume( )
         subordinate = self._parseObject( )
         lexVal = LList( LSymbol('BACKQUOTE'), subordinate )
      elif nextToken == LypsScanner.COMMA_TOK:
         lex = self._scanner.getLexeme( )
         self._scanner.consume( )
         subordinate = self._parseObject( )
         lexVal = LList( LSymbol('COMMA'), subordinate )
      elif nextToken == LypsScanner.COMMA_AT_TOK:
         lex = self._scanner.getLexeme( )
         self._scanner.consume( )
         subordinate = self._parseObject( )
         lexVal = LList( LSymbol('COMMA-AT'), subordinate )
      elif nextToken in ( LypsScanner.OPEN_BRACKET_TOK, LypsScanner.CLOSE_BRACKET_TOK,
                          LypsScanner.POUND_SIGN_TOK, LypsScanner.PIPE_TOK, LypsScanner.COLON_TOK ):
         lex = self._scanner.getLexeme( )
         lexVal = lex
         self._scanner.consume( )
      elif nextToken == LypsScanner.EOF_TOK:
         lexVal = None
      else:
         raise Parser.ParseError( self._scanner, 'Object expected.' )

      return lexVal

   def _parseList( self ) -> LList:
      theList = [ ]

      # Open List
      if self._scanner.peekToken( ) != LypsScanner.OPEN_PAREN_TOK:
         raise Parser.ParseError( self._scanner, '( expected.' )
      else:
         self._scanner.consume( )

      # List Entries
      while self._scanner.peekToken( ) not in (LypsScanner.CLOSE_PAREN_TOK,
                                               LypsScanner.EOF_TOK):
         theList.append( self._parseObject( ) )

      # Close List
      if self._scanner.peekToken( ) != LypsScanner.CLOSE_PAREN_TOK:
         raise Parser.ParseError( self._scanner, ') expected.')
      else:
         self._scanner.consume( )

      return LList( *theList )

if __name__ == '__main__':
   xy = LypsParser( )

   def test( anExpr ):
      print( '\n>>> ', anExpr )
      expr = xy.parse( anExpr )
      print( expr )

   test( '(one two three)' )
   test( '(one (two three) four)' )
   test( '((one) two)' )

