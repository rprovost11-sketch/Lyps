from LypsAST import ( LSymbol, LList, LMap, LFunction, LPrimitive, LMacro,
                       prettyPrintLypsExpr )
from LypsParser import LypsParser
import ltk_py3.Listener as Listener
from ltk_py3.SymbolTable import SymbolTable

import functools
import math
import fractions
import sys
from typing import Callable, Any, Dict, List


class LypsRuntimeError( Exception ):
   def __init__( self, *args ) -> None:
      super().__init__( self, *args )


class LypsRuntimeFuncError( LypsRuntimeError ):
   def __init__( self, lypsCallable: Callable[[SymbolTable], Any], errorMsg: str ) -> None:
      assert isinstance(lypsCallable, LPrimitive)
      fnName = lypsCallable._name
      usage = lypsCallable._usage
      errStr = f"ERROR '{fnName}': {errorMsg}\nUSAGE: {usage}" if usage else f"ERROR '{fnName}': {errorMsg}"
      super().__init__( errStr )


LNULL = LList( )
L_NUMBER = (int,float,fractions.Fraction)
L_ATOM   = (int,float,fractions.Fraction,str)

class LypsInterpreter( Listener.Interpreter ):
   def __init__( self ) -> None:
      self._parser: LypsParser = LypsParser( )
      primitiveDict: Dict[str, Any] = LypsInterpreter.constructPrimitives( self._parser.parse )
      self._env:SymbolTable = SymbolTable( parent=None, **primitiveDict )

   def reboot( self ) -> None:
      primitiveDict = LypsInterpreter.constructPrimitives( self._parser.parse )
      self._env = self._env.reInitialize( **primitiveDict )

   def eval( self, inputExprStr: str ) -> str:
      ast = self._parser.parse( inputExprStr )
      resultExpr = LypsInterpreter._lEval( self._env, ast )
      return prettyPrintLypsExpr( resultExpr ).strip()

   def runtimeLibraries( self ) -> List[str]:
      return [ 'Library.lyps' ]

   def testFileList( self ) -> List[str]:
      return [ 'test01-calculations.lyps',          # Test primitive operations
               'test02-variables.lyps',             # Test variables and blocks
               #'test03-functions.lyps',
               'test04-dataTypes.lyps',
               'test05-controlStructs.lyps',
               #'test99-misc.lyps',
               ]

   @staticmethod
   def _lTrue( lypsExpr: Any ) -> bool:
      if isinstance(lypsExpr, (LList, list)):
         return len(lypsExpr) != 0
      elif isinstance(lypsExpr, int):
         return lypsExpr != 0
      else:
         return True

   @staticmethod
   def _lEval( env: SymbolTable, lypsExpr: Any, *args, **keys ) -> Any:
      '''Evaluate expr as a lyps expression.
      Note:  Symbols (including function names) need to be in capitals before
      invoking this function.
      '''
      if lypsExpr is None:
         return LList( )
      elif isinstance( lypsExpr, L_ATOM ):
         return lypsExpr
      elif isinstance( lypsExpr, LSymbol ):
         try:
            result = env.getValue( lypsExpr._val )
            return lypsExpr if result is None else result
         except:
            return lypsExpr
      elif  isinstance( lypsExpr, LList ):
         if len(lypsExpr._list) == 0:
            return LList( )

         evaluatedKeys: Dict[str, Any] = { }

         # Break the list contents into a function and a list of args
         try:
            primary, *exprArgs = lypsExpr._list
         except:
            raise LypsRuntimeError( 'Badly formed list expression.' )

         if not isinstance( primary, (LList,LSymbol) ):
            raise LypsRuntimeError( f'Badly formed list expression.  The first element should be a symbol or function.' )

         # fn is an LPrimitive, LFunction or a function name symbol
         # Use this information to get the function definition
         fnDef = LypsInterpreter._lEval( env, primary )
         if not isinstance( fnDef, (LPrimitive, LFunction, LMacro) ):
            raise LypsRuntimeError( 'Badly formed list expression.  The first element should evaluate to a primitive or function.' )

         fnName = primary if isinstance(primary, LSymbol) else fnDef._name

         # Determine if the function uses the standard evaluation order for arguments
         if not fnDef._stdEvalOrd:
            return fnDef( LypsInterpreter._lEval, env, *exprArgs, **evaluatedKeys )

         # Evaluate each arg
         evaluatedArgs = [ ]
         for argNum,argExpr in enumerate(exprArgs):
            evaluatedArg = LypsInterpreter._lEval( env, argExpr )
            evaluatedArgs.append( evaluatedArg )

         try:
            return fnDef( LypsInterpreter._lEval, env, *evaluatedArgs, **evaluatedKeys )
         except TypeError:
            raise LypsRuntimeError( f'Error evaluating list expression {fnName}.' )
      elif  isinstance( lypsExpr, LMap ):
         return lypsExpr
      elif  isinstance( lypsExpr, LFunction ):
         env = env.openScope( )

         # store the arguments as locals
         for paramName, argVal in zip( lypsExpr._params._list, args ):
            env.defLocal( str(paramName), argVal )

         # evaluate the body expressions.  Return the result of the last
         # body expression evaluated.
         latestResult = None
         for expr in lypsExpr._body:
            if isinstance(expr, (LPrimitive, LFunction, LMap, LList, LSymbol)):
               latestResult = LypsInterpreter._lEval( env, expr )
            else: # expr should be an L_Atom (int,float,Fraction,str)
               latestResult = expr

         #env = env.closeScope( ) # occurs automatically when env goes out of scope
         return latestResult
      elif isinstance( lypsExpr, LMacro ):
         env = env.openScope( )

         # store the arguments as locals
         for paramName, argVal in zip( lypsExpr._params._list, args ):
            env.defLocal( str(paramName), argVal )

         resultExpr = LypsInterpreter._lEval( env, lypsExpr._body )

         #env = env.closeScope( ) # occurs automatically when env goes out of scope
         return resultExpr
      else:
         raise LypsRuntimeError( 'Unknown lyps expression type.' )

   @staticmethod
   def macroexpand( env: SymbolTable, expr: Any ) -> Any:
      pass

   @staticmethod
   def backquote_expand( env: SymbolTable, expr: Any ):
      if isinstance( expr, LList ):
         if len(expr._list) == 0:
            return LList( )

         primary = expr[0]
         if (primary == LSymbol('COMMA')) or (primary == LSymbol('COMMA-AT')):
            return LypsInterpreter._lEval(env, expr)

         resultList = [ ]
         for listElt in expr:
            resultListElt = LypsInterpreter.backquote_expand( env, listElt )
            resultList.append( resultListElt )
         return LList( *resultList )
      else:
         return expr

   @staticmethod
   def constructPrimitives( parseLypsString: Callable[[str], Any] ) -> Dict[str, Any]:
      global LNULL
      primitiveDict = { }
      INSIDE_BACKQUOTE = False

      class LDefPrimitive( object ):
         def __init__( self, primitiveSymbol: str, args: str, standardEvalOrder: bool=True ) -> None:
            '''standardEvalOrder indicates that this function evaluates its
            arguments in the usual way.  That is arguments each get evaluated
            in order of occurrence and the results of those valuations are
            passed to the function as the arguments.  False indicates that
            the evaluation order of the arguments is handled by the primitive.
            '''
            self._name:str  = primitiveSymbol.upper( )
            self._usage:str = f'({primitiveSymbol} {args})' if args else ''
            self._stdEvalOrd:bool = standardEvalOrder

         def __call__( self, primitiveDef ):
            nonlocal primitiveDict
            lPrimitivObj = LPrimitive( primitiveDef, self._name,
                                       self._usage, self._stdEvalOrd )
            primitiveDict[ self._name ] = lPrimitivObj
            return lPrimitivObj

      # ###################################
      # Lyps Object & Primitive Definitions
      # ###################################
      LNULL = LList( )
      primitiveDict[ 'NULL' ] = LNULL
      primitiveDict[ 'PI'   ] = math.pi
      primitiveDict[ 'E'    ] = math.e
      primitiveDict[ 'INF'  ] = math.inf
      primitiveDict[ '-INF' ] = -math.inf
      primitiveDict[ 'NAN'  ] = math.nan

      # =================
      # Symbol Definition
      # -----------------
      @LDefPrimitive( 'def!', '\'<symbol> <object>' )                                                   # (def! '<symbol> <expr> )  ;; Define a var in the local symbol table
      def LP_defLocal( env, *args, **keys ):
         try:
            key,val = args
         except:
            raise LypsRuntimeFuncError( LP_defLocal, '2 arguments expected.', )

         try:
            if isinstance( val, LFunction ):
               val.setName( key )

            return env.defLocal( str(key), val )
         except:
            raise LypsRuntimeFuncError( LP_defLocal, 'Unknown error.' )

      @LDefPrimitive( 'def!!', '\'<symbol> <object>' )                         # (def!! '<symbol> <expr> ) ;; Define a var in the global symbol table
      def LP_defGlobal( env, *args, **keys ):
         if len(args) != 2:
            raise LypsRuntimeFuncError( LP_defGlobal, '2 arguments expected.' )

         key,val = args
         try:
            if isinstance( val, LFunction ):
               val.setName( key )

            return env.defGlobal( str(key), val)
         except:
            raise LypsRuntimeFuncError( LP_defGlobal, 'Unknown error.' )

      @LDefPrimitive( 'defun!', '<symbol> (<param1> <param2> ...) <expr1> <expr2> ...', standardEvalOrder=False )
      def LP_defunLocal( env, *args, **keys ):
         try:
            fnName, funcParams, *funcBody = args
         except:
            raise LypsRuntimeFuncError( LP_defunLocal, "3 or more arguments expected." )

         if not isinstance( fnName, LSymbol ):
            raise LypsRuntimeFuncError( LP_defunLocal, "Argument 1 expected to be a symbol." )

         if not isinstance( funcParams, LList ):
            raise LypsRuntimeFuncError( LP_defunLocal, "Argument 2 expected to be a list of symbols." )

         theFunc = LFunction( fnName, funcParams, funcBody )
         assert isinstance( env, SymbolTable )
         env.defLocal( str(fnName), theFunc )
         return theFunc

      @LDefPrimitive( 'defun!!', '<symbol> (<param1> <param2> ...) <expr1> <expr2> ...', standardEvalOrder=False )
      def LP_defunGlobal( env, *args, **keys ):
         try:
            fnName, funcParams, *funcBody = args
         except:
            raise LypsRuntimeFuncError( LP_defunGlobal, "3 or more arguments expected." )

         if not isinstance( fnName, LSymbol ):
            raise LypsRuntimeFuncError( LP_defunGlobal, "Argument 1 expected to be a symbol." )

         if not isinstance( funcParams, LList ):
            raise LypsRuntimeFuncError( LP_defunGlobal, "Argument 2 expected to be a list of symbols." )

         theFunc = LFunction( fnName, funcParams, funcBody )
         assert isinstance( env, SymbolTable )
         env.defGlobal( str(fnName), theFunc )
         return theFunc

      @LDefPrimitive( 'defmacro!!', '<symbol> (<param1> <param2> ...) <expr1> <expr2> ...', standardEvalOrder=False )
      def LP_defmacro( env, *args, **keys ):
         try:
            fnName, funcParams, *funcBody = args
         except:
            raise LypsRuntimeFuncError( LP_defunGlobal, "3 or more arguments expected." )

         if not isinstance( fnName, LSymbol ):
            raise LypsRuntimeFuncError( LP_defunGlobal, "Argument 1 expected to be a symbol." )

         if not isinstance( funcParams, LList ):
            raise LypsRuntimeFuncError( LP_defunGlobal, "Argument 2 expected to be a list of symbols." )

         theFunc = LMacro( fnName, funcParams, funcBody )
         assert isinstance( env, SymbolTable )
         env.defGlobal( str(fnName), theFunc )
         return theFunc

      @LDefPrimitive( 'set!', '\'<symbol> <object>' )                          # (set! '<symbol> <expr> )  ;; Set a variable.  If doesn't already exist make a local.
      def LP_set( env, *args, **keys ):
         assert isinstance( env, SymbolTable )

         if len(args) != 2:
            raise LypsRuntimeFuncError( LP_set, '2 arguments expected.' )

         key,val = args
         key = str(key)
         try:
            if isinstance( val, LFunction ):
               val.setName( key )

            # If key exists somewhere in the symbol table hierarchy, set its
            # value to val.  If it doesn't exist, define it in the local-most
            # symbol table and set its value to val.
            theSymTab = env.findDef( key )
            if not theSymTab:
               theSymTab = env    # set theSymTab to the local-most scope
            theSymTab.defLocal( key, val )
            return val
         except:
            raise LypsRuntimeFuncError( LP_set, 'Unknown error.' )

      @LDefPrimitive( 'undef!', '\'<symbol>' )                                 # (undef! '<symbol>)   ;; undefine the most local definition for <name>
      def LP_undef( env, *args, **keys ):
         if len(args) == 1:
            key = args
         else:
            raise LypsRuntimeFuncError( LP_undef, '1 argument exptected.' )

         try:
            env.undef( str(key) )
            return LNULL
         except:
            raise LypsRuntimeFuncError( LP_undef, 'Unknown error.' )

      @LDefPrimitive( 'symtab!', '')                                           # (symtab!)
      def LP_symtab( env, *args, **keys ):
         print( 'Symbol Table Dump:  Inner-Most Scope First')
         print( '------------------------------------------')
         try:
            while env:
               symList = env.localSymbols()
               print( symList )
               env = env.parentEnv()
         except:
            pass

         return LNULL

      # ==================
      # Control Structures
      # ------------------
      @LDefPrimitive( 'lam', '(<param1> <param2> ... ) <expr1> <expr2> ...', standardEvalOrder=False )
      def LP_lam( env, *args, **keys ):
         try:
            funcParams, *funcBody = args
         except ValueError:
            raise LypsRuntimeFuncError( LP_lam, '2 arguments expected.' )

         return LFunction( LSymbol(""), funcParams, funcBody )

      @LDefPrimitive( 'block', '<expr1> <expr2> ...)', standardEvalOrder=False )                         # (block <expr1> <expr2> ...)     ;; execute the sequence of expr's in a nested scope
      def LP_block( env, *args, **keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_block, '1 or more arguments expected.' )

         env = env.openScope( )

         lastResult = LNULL
         for expr in args:
            lastResult = LypsInterpreter._lEval( env, expr )

         env = env.closeScope( )

         return lastResult

      @LDefPrimitive( 'if', '<cond> <conseq> [<alt>]', standardEvalOrder=False )                     # (if <cond> <conseq> [<alt>])     ;; If statement
      def LP_if( env, *args, **keys ):
         numArgs = len(args)
         if not(2 <= numArgs <= 3):
            raise LypsRuntimeFuncError( LP_if, '2 or 3 arguments expected.' )

         condExpr,*rest = args

         try:
            condResult = LypsInterpreter._lEval( env, condExpr )
            if LypsInterpreter._lTrue(condResult):
               return LypsInterpreter._lEval( env, rest[0])    # The THEN part
            elif numArgs == 3:
               return LypsInterpreter._lEval( env, rest[1])    # The ELSE part
            else:
               return LNULL
         except:
            raise LypsRuntimeFuncError( LP_if, 'Unknown error.' )

      @LDefPrimitive( 'cond', '(<cond1> <expr1>) (<cond2> <expr2>)', standardEvalOrder=False )     # (cond (<cond1> <expr1>) (<cond2> <expr2>) ...)
      def LP_cond( env, *args, **keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_cond, '1 or more argument exptected.' )

         caseList = args
         for caseNum,case in enumerate(caseList):
            assert isinstance(case, LList)
            try:
               testExpr,bodyExpr = case._list
            except ValueError:
               raise LypsRuntimeFuncError( LP_cond, f"Entry {caseNum+1} does not contain a (<cond:expr> <body:expr>) pair." )

            if LypsInterpreter._lTrue(LypsInterpreter._lEval(env,testExpr)):
               return LypsInterpreter._lEval( env, bodyExpr )

         return LList( )

      @LDefPrimitive( 'case', '<expr> (<val1> <expr1>) (<val2> <expr2>) ...)', standardEvalOrder=False )  # (case <expr> (<val1> <expr1>) (<val2> <expr2>) ...)
      def LP_case( env, *args, **keys ):
         try:
            expr, *caseList = args
         except ValueError:
            raise LypsRuntimeFuncError( LP_case, '2 or more arguments exptected.' )

         exprVal = LypsInterpreter._lEval( env, expr )

         for caseNum,case in enumerate(caseList):
            try:
               caseVal,caseExpr = case._list
            except ValueError:
               raise LypsRuntimeFuncError( LP_case, "Entry {0} does not contain a (<val> <expr>) pair.".format(caseNum+1) )

            if LypsInterpreter._lEval(env,caseVal) == exprVal:
               return LypsInterpreter._lEval( env, caseExpr )

         return LNULL

      @LDefPrimitive( 'quote', '<expr>', standardEvalOrder=False )                                       # (quote <expr>)                     ;; return <expr> without evaluating it
      def LP_quote( env, *args, **keys ):
         if (len(args) != 1):
            raise LypsRuntimeFuncError( LP_quote, '1 argument exptected.' )

         return args[0]

      @LDefPrimitive( 'backquote', '<expr>', standardEvalOrder=False )
      def LP_backquote( env, *args, **keys ):
         nonlocal INSIDE_BACKQUOTE
         if (len(args) != 1):
            raise LypsRuntimeFuncError( LP_backquote, '1 argument exptected.' )

         lypsExpr = args[0]

         if INSIDE_BACKQUOTE:
            raise LypsRuntimeFuncError( LP_backquote, 'Cannot nest backquotes.')

         INSIDE_BACKQUOTE = True

         try:
            expandedForm = LypsInterpreter.backquote_expand( env, lypsExpr )
         finally:
            INSIDE_BACKQUOTE = False

         return expandedForm

      @LDefPrimitive( 'comma', '<expr>', standardEvalOrder=False )
      def LP_comma( env, *args, **keys ):
         nonlocal INSIDE_BACKQUOTE
         if (len(args) != 1):
            raise LypsRuntimeFuncError( LP_comma, '1 argument exptected.' )

         if not INSIDE_BACKQUOTE:
            raise LypsRuntimeFuncError( LP_comma, 'COMMA can only occur inside a BACKQUOTE.')

         subordinateExpr = args[0]
         result = LypsInterpreter._lEval( env, subordinateExpr )
         return result

      @LDefPrimitive( 'comma-at', '<expr>', standardEvalOrder=False )
      def LP_comma_at( env, *args, **keys ):
         nonlocal INSIDE_BACKQUOTE
         if (len(args) != 1):
            raise LypsRuntimeFuncError( LP_comma_at, '1 argument exptected.' )

         if not INSIDE_BACKQUOTE:
            raise LypsRuntimeFuncError( LP_comma, 'COMMA-AT can only occur inside a BACKQUOTE.')

         subordinateExpr = args[0]
         result = LypsInterpreter._lEval( env, subordinateExpr )
         return result

      @LDefPrimitive( 'while', '<conditionExpr> <bodyExpr>', standardEvalOrder=False )                            # (while <conditionExpr> <bodyExpr>)  ;; repeatedly evaluate body while condition is true.
      def LP_while( env, *args, **kyes ):
         try:
            conditionExpr, bodyExpr = args
         except ValueError:
            raise LypsRuntimeFuncError( LP_while, '2 arguments expected.' )

         latestResult = LList( )

         try:
            condResult = LypsInterpreter._lEval(env, conditionExpr)
            while LypsInterpreter._lTrue( condResult ):
               latestResult = LypsInterpreter._lEval( env, bodyExpr )
               condResult = LypsInterpreter._lEval(env, conditionExpr )

         except Exception:
            raise LypsRuntimeFuncError( LP_while, "Error evaluating condition for while loop." )

         return latestResult

      @LDefPrimitive( 'eval', '<expr>' )                                       # (eval '<expr>)                     ;; evaluate <expr>
      def LP_eval( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_eval, '1 argument exptected.' )

         return LypsInterpreter._lEval( env, args[0] )

      @LDefPrimitive( 'parse', '<lypsExpressionString>')
      def LP_parse( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_parse, '1 string argument expected.' )

         theExprStr = args[0]
         theExprAST = parseLypsString( theExprStr )
         return theExprAST

      @LDefPrimitive( 'pprint', '<lypsExpr>' )
      def LP_pprint( env, *args, **keys) :
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_pprint, '1 lyps object argument expected.' )

         theExpr = args[0]
         prettyPrintLypsExpr( theExpr )
         return theExpr

      # =======================
      # List & Map Manipulation
      # -----------------------
      @LDefPrimitive( 'list', '<expr1> <expr2> ...')                           # (list <expr1> <expr2> ...)         ;; return a list of evaluated expressions
      def LP_list( env, *args, **Keys ):
         if len(args) == 0:
            raise LypsRuntimeFuncError( LP_list, '1 or more arguments expected.' )

         theLst = [ ]

         for exprNum,expr in enumerate(args):
            theLst.append( expr )

         return LList( *theLst )

      @LDefPrimitive( 'first', '<list>' )                                      # (first <list>)                     ;; return the first item in the list
      def LP_first( env, *args, **Keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_first, '1 argument expected.' )

         theList = args[0]
         if not isinstance(theList, LList):
            raise LypsRuntimeFuncError( LP_first, '1st argument expected to be a list.' )

         try:
            return theList.first()
         except IndexError:
            return LList( )

      @LDefPrimitive( 'rest', '<list>' )                                       # (rest <list>)                      ;; return the list without the first item
      def LP_rest( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_rest, '1 argument expected.', usage='(rest <list>)' )

         theList = args[0]
         return theList.rest()

      @LDefPrimitive( 'cons', '\'<obj> \'<list>' )                             # (cons '<obj> '<list>)              ;; return the list with <obj> inserted into the front
      def LP_cons( env, *args, **keys ):
         try:
            arg1,arg2 = args
         except:
            raise LypsRuntimeFuncError( LP_cons, '2 arguments exptected.' )

         try:
            copiedList = arg2.copy( )
            copiedList.insert( 0, arg1 )
         except:
            raise LypsRuntimeFuncError( LP_cons, 'Invalid argument.' )

         return copiedList

      @LDefPrimitive( 'push!', '\'<list> \'<value>' )                          # (push! '<list> <value>)
      def LP_push( env, *args, **keys ):
         try:
            alist, value = args
         except Exception:
            raise LypsRuntimeFuncError( LP_push, '2 arguments exptected.' )

         try:
            if isinstance(alist, LList):
               alist._list.append( value )
            else:
               alist = LNULL
         except:
            raise LypsRuntimeFuncError( LP_push, 'Invalid argument.' )

         return alist

      @LDefPrimitive( 'pop!', '\'<list>' )                                     # (pop! '<list>)
      def LP_pop( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_pop, '1 argument expected.' )

         alist = args[0]

         try:
            value = alist._list.pop()
         except:
            raise LypsRuntimeFuncError( LP_pop, 'Invalid argument.' )

         return value

      @LDefPrimitive( 'at', '\'<listORMap> \'<keyOrIndex>' )                   # (at '<listOrMap> '<keyOrIndex>)
      def LP_at( env, *args, **keys ):
         try:
            keyed,key = args
         except:
            raise LypsRuntimeFuncError( LP_at, '2 arguments expected.' )

         if isinstance(keyed, LList):
            keyed = keyed._list
         elif isinstance(keyed, LMap):
            keyed = keyed._dict
         else:
            raise LypsRuntimeFuncError( LP_at, 'Invalid argument.  List or Map expected.' )

         if isinstance(key, LSymbol):
            key = key._val

         try:
            value = keyed[ key ]
         except:
            raise LypsRuntimeFuncError( LP_at, 'Invalid argument key/index.' )

         return value

      @LDefPrimitive( 'atSet!', '<listOrMap> <keyOrIndex> <value>' )           # (atSet! <listOrMap> <keyOrIndex> <value>)
      def LP_atSet( env, *args, **keys ):
         try:
            keyed,key,value = args
         except:
            raise LypsRuntimeFuncError( LP_atSet, '3 arguments expected.' )

         if isinstance(keyed, LList):
            keyed = keyed._list
         elif isinstance(keyed, LMap):
            keyed = keyed._dict
         else:
            raise LypsRuntimeFuncError( LP_atSet, 'Invalid argument.  List or map expeced as first argument.' )

         if isinstance(key, LSymbol):
            key = key._val

         try:
            keyed[ key ] = value
         except:
            raise LypsRuntimeFuncError( LP_atSet, 'Invalid argument key/index.' )

         return value


      @LDefPrimitive( 'join', '\'<list1> \'<list2>' )                          # (join '<list-1> '<list-2>)
      def LP_join( env, *args, **keys ):
         try:
            arg1,arg2 = args
         except:
            raise LypsRuntimeFuncError( LP_join, '2 arguments expected' )

         if isinstance( arg1, LList ) and isinstance( arg2, LList ):
            newList = arg1._list + arg2._list
            return LList( *newList )
         else:
            raise LypsRuntimeFuncError( LP_join, 'Invalid argument.' )

      @LDefPrimitive( 'hasValue?', '\'<listOrMap> \'<value>' )                 # (hasValue? '<listOrMap> '<value>)
      def LP_hasValue( env, *args, **keys ):
         try:
            keyed,aVal = args
         except:
            raise LypsRuntimeFuncError( LP_hasValue, '2 arguments expected.' )

         if isinstance(keyed, LList):
            keyed = keyed._list
         elif isinstance(keyed, LMap):
            keyed = keyed._dict.values()
         else:
            raise LypsRuntimeFuncError( LP_hasValue, 'Invalid argument.  Argument 1 expected to be a list or map.')

         try:
            return 1 if aVal in keyed else 0
         except:
            raise LypsRuntimeFuncError( LP_hasValue, 'Invalid argument.')

      @LDefPrimitive( 'map', '(<key1> <val1>) (<key2> <val>2) ...', standardEvalOrder=False )       # (map (<key1> <val1>) (<key2> <val2>) ...)  ;; construct a map of key-value pairs
      def LP_map( env, *args, **keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_map, '1 or more arguments exptected.' )

         theMapping = { }

         for entryNum,key_expr_pair in enumerate(args):
            try:
               key,expr =  key_expr_pair
            except:
               raise LypsRuntimeFuncError( LP_map, f'Entry {entryNum + 1} does not contain a (key value) pair.' )

            if isinstance( key, (int,float,str,LSymbol) ):
               theMapping[ str(key) ] = LypsInterpreter._lEval( env, expr)
            else:
               raise LypsRuntimeFuncError( LP_map, f'Entry {entryNum+1} has an invalid <key> type.' )


         theLMapInst = LMap( aMap=theMapping )
         return theLMapInst

      @LDefPrimitive( 'update!', '<map1> <map2>' )                             # (update! <map1> <map2>)                    ;; merge map2's data into map1
      def LP_update( env, *args, **keys ):
         try:
            map1,map2 = args
         except:
            raise LypsRuntimeFuncError( LP_update, '2 arguments exptected.' )

         try:
            map1._dict.update( map2._dict )
            return map1
         except:
            raise LypsRuntimeFuncError( LP_update, 'Invalid argument.' )

      @LDefPrimitive( 'hasKey?', '<map> <key>' )                               # (hasKey? <map> <key>)
      def LP_hasKey( env, *args, **keys ):
         try:
            aMap,aKey = args
         except:
            raise LypsRuntimeFuncError( LP_hasKey, '2 arguments expected.' )

         if isinstance(aMap, LMap):
            aMap = aMap._dict
         else:
            raise LypsRuntimeFuncError( LP_hasKey, 'Invalid argument 1.  Map expected.')

         if isinstance(aKey, LSymbol):
            aKey = aKey._val

         try:
            return 1 if aKey in aMap else 0
         except:
            raise LypsRuntimeFuncError( LP_hasKey, 'Invalid argument.' )

      # =====================
      # Arithmetic Operations
      # ---------------------
      @LDefPrimitive( '+', '<expr1> <expr2> ...')                              # (+ <val1> <val2>)
      def LP_add( env, *args, **keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_add, '1 or more arguments expected.' )

         try:
            return sum(args)
         except:
            raise LypsRuntimeFuncError( LP_add, 'Invalid argument.' )

      @LDefPrimitive( '-', '<expr1> <expr2> ...')                              # (- <val1> <val2>)
      def LP_sub( env, *args, **keys ):
         argct = len(args)
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_sub, '1 or more arguments expected.' )

         try:
            if argct == 1:
               return -1 * args[0]
            else:
               return functools.reduce( lambda x,y: x - y, args )
         except:
            raise LypsRuntimeFuncError( LP_sub, 'Invalid argument.' )

      @LDefPrimitive( '*', '<expr1> <expr2> ...' )                             # (* <val1> <val2>)
      def LP_mul( env, *args, **keys ):
         if len(args) < 2:
            raise LypsRuntimeFuncError( LP_mul, '2 or more arguments exptected.' )

         try:
            return functools.reduce( lambda x,y: x * y, iter(args) )
         except:
            raise LypsRuntimeFuncError( LP_mul, 'Invalid argument.' )

      @LDefPrimitive( '/', '<expr1> <expr2> ...' )                             # (/ <val1> <val2>)
      def LP_div( env, *args, **keys ):
         if len(args) < 2:
            raise LypsRuntimeFuncError( LP_div, '2 or more arguments exptected.' )

         try:
            return functools.reduce( lambda x,y: x / y, iter(args) )
         except:
            raise LypsRuntimeFuncError( LP_div, 'Invalid argument.' )

      @LDefPrimitive( '//', '<expr1> <expr>')                                  # (// <val1> <val2>)
      def LP_intdiv( env, *args, **keys ):
         if len(args) != 2:
            raise LypsRuntimeFuncError( LP_intdiv, '2 arguments expected.' )

         try:
            return args[0] // args[1]
         except:
            raise LypsRuntimeFuncError( LP_intdiv, 'Invalid argument.' )

      @LDefPrimitive( 'mod', '<expr1> <expr>')                                 # (mod <val1> <val2>)
      def LP_moddiv( env, *args, **keys ):
         if len(args) != 2:
            raise LypsRuntimeFuncError( LP_moddiv, '2 arguments expected.' )

         try:
            return args[0] % args[1]
         except:
            raise LypsRuntimeFuncError( LP_moddiv, 'Invalid argument.' )

      @LDefPrimitive( 'trunc', '<expr>')                                       # (trunc <expr>)
      def LP_trunc( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_trunc, '1 argument exptected.' )

         try:
            return int(*args)
         except:
            raise LypsRuntimeFuncError( LP_trunc, 'Invalid argument.' )

      @LDefPrimitive( 'abs', '<expr>')                                         # (abs <val>)
      def LP_abs( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_abs, '1 argument exptected.' )

         try:
            return abs(*args)
         except:
            raise LypsRuntimeFuncError( LP_abs, 'Invalid argument.' )

      @LDefPrimitive( 'log', '<expr> [ <base> ]')                              # (log <x> [<base>])                         ;; if base is not provided, 10 is used.
      def LP_log( env, *args, **keys ):
         numArgs = len(args)
         if not( 1 <= numArgs <= 2 ):
            raise LypsRuntimeFuncError( LP_log, '1 or 2 arguments exptected.' )

         try:
            num,*rest = args
            base = 10 if len(rest) == 0 else rest[0]
            return math.log(num,base)
         except:
            raise LypsRuntimeFuncError( LP_log, 'Invalid argument.' )

      @LDefPrimitive( 'pow', '<base> <power>')                                 # (pow <base> <power>)
      def LP_pow( env, *args, **keys ):
         if len(args) != 2:
            raise LypsRuntimeFuncError( LP_pow, '2 arguments expected.' )

         try:
            base,power = args
            return base ** power
         except:
            raise LypsRuntimeFuncError( LP_pow, 'Invalid argument.' )

      @LDefPrimitive( 'sin', '<radians>')                                      # (sin <radians>)
      def LP_sin( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_sin, '1 argument expected.' )

         try:
            return math.sin(*args)
         except:
            raise LypsRuntimeFuncError( LP_sin, 'Invalid argument.' )

      @LDefPrimitive( 'cos', '<radians>')                                      # (cos <radians>)
      def LP_cos( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_cos, '1 argument expected.' )

         try:
            return math.cos(*args)
         except:
            raise LypsRuntimeFuncError( LP_cos, 'Invalid argument.' )

      @LDefPrimitive( 'tan', '<radians>' )                                     # (tan <radians>)
      def LP_tan( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_tan, '1 argument expected.' )

         try:
            return math.tan(*args)
         except:
            raise LypsRuntimeFuncError( LP_tan, 'Invalid argument.' )

      @LDefPrimitive( 'exp', '<number>' )                                      # (exp <pow:number>)
      def LP_exp( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_exp, '1 argument expected.' )

         try:
            return math.exp(*args)
         except:
            raise LypsRuntimeFuncError( LP_exp, 'Invalid Argument.' )

      @LDefPrimitive( 'min', '<val1> <val2> ...')                              # (min <val1> <val2> ...)
      def LP_min( env, *args, **Keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_min, '1 or more arguments exptected.' )

         try:
            return min( *args )
         except:
            raise LypsRuntimeFuncError( LP_min, 'Invalid argument.' )

      @LDefPrimitive( 'max', '<val1> <val2> ...')                              # (max <val1> <val2> ...)
      def LP_max( env, *args, **keys ):
         if len(args) < 1:
            raise LypsRuntimeFuncError( LP_max, '1 or more arguments exptected.' )

         try:
            return max( *args )
         except:
            raise LypsRuntimeFuncError( LP_max, 'Invalid argument.' )

      # ==========
      # Predicates
      # ----------
      @LDefPrimitive( 'isNull?', '<expr>')                                     # (isNull? <expr>)
      def LP_isNull( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isNull, '1 argument expected.' )

         arg1 = args[0]
         return 1 if (isinstance(arg1,LList) and (len(arg1) == 0)) else 0

      @LDefPrimitive( 'isNumber?', '<expr>')                                   # (isNumber?  <expr>)
      def LP_isNumber( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isNumber, '1 argument expected.' )

         return 1 if isinstance( args[0], L_NUMBER ) else 0

      @LDefPrimitive( 'isSymbol?', '<expr>')                                   # (isSymbol?  <expr>)
      def LP_isSym( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isSym, '1 argument expected.' )

         return 1 if isinstance( args[0], LSymbol ) else 0

      @LDefPrimitive( 'isAtom?', '<expr>')                                     # (isAtom? <expr>) -> 1 if expr in { int, float, fraction, string }
      def LP_isAtom( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isAtom, '1 argument expected.' )

         return 1 if isinstance( args[0], L_ATOM ) else 0

      @LDefPrimitive( 'isList?', '<expr>')                                     # (isList? <expr>)
      def LP_isList( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isList, '1 argument expected.' )

         return 1 if isinstance( args[0], LList ) else 0

      @LDefPrimitive( 'isMap?', '<expr>')                                      # (isMap?  <expr>)
      def LP_isMap( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isMap, '1 argument expected.' )

         return 1 if isinstance( args[0], LMap ) else 0

      @LDefPrimitive( 'isString?', '<expr>')                                   # (isString?  <expr>)
      def LP_isStr( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isStr, '1 argument expected.' )

         return 1 if isinstance( args[0], str ) else 0

      @LDefPrimitive( 'isFunction?', '<expr>')                                 # (isFunction? <expr>)
      def LP_isCall( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_isCall, '1 argument expected.' )

         return 1 if isinstance( args[0], (LPrimitive,LFunction) ) else 0

      # ====================
      # Relational Operators
      # --------------------
      @LDefPrimitive( 'is?', '<expr1> <expr2>')                                # (is? <val1> <val2>)      Are the two values the same object?
      def LP_is( env, *args, **keys ):
         try:
            arg1,arg2 = args
         except:
            raise LypsRuntimeFuncError( LP_is, '2 arguments exptected.' )

         if isinstance(arg1, (int,float,str)):
            return 1 if (arg1 == arg2) else 0
         else:
            return 1 if (arg1 is arg2) else 0

      @LDefPrimitive( '=', '<expr1> <expr2> ...')                              # (=   <val1> <val2> ...)    Are all the values equal?
      def LP_equal( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_equal, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 == arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_equal, 'Unknown error.' )

      @LDefPrimitive( '<>', '<expr1> <expr2> ...')                             # (<>  <val1> <val2> ...)
      def LP_notEqual( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_notEqual, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 != arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_notEqual, 'Unknown error.' )

      @LDefPrimitive( '<', '<expr1> <expr2> ...')                              # (<   <val1> <val2> ...)
      def LP_less( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_less, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 < arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_less, 'Unknown error.' )

      @LDefPrimitive( '<=', '<expr1> <expr2> ...' )                            # (<=  <val1> <val2> ...)
      def LP_lessOrEqual( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_lessOrEqual, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 <= arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_lessOrEqual, 'Unknown error.' )

      @LDefPrimitive( '>', '<expr1> <expr2> ...' )                             # (>   <val1> <val2> ...)
      def LP_greater( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_greater, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 > arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_greater, 'Unknown error.' )

      @LDefPrimitive( '>=', '<expr1> <expr2> ...' )                            # (>=  <val1> <val2> ...)
      def LP_greaterOrEqual( env, *args, **keys ):
         numArgs = len(args)
         if numArgs < 2:
            raise LypsRuntimeFuncError( LP_greaterOrEqual, '2 or more arguments expected.' )

         pairs = [ ]
         prior = None
         for mbr in args:
            if prior is not None:
               pairs.append( (prior,mbr) )
            prior = mbr

         try:
            for arg1,arg2 in pairs:
               if not( arg1 >= arg2 ):
                  return 0

            return 1
         except:
            raise LypsRuntimeFuncError( LP_greaterOrEqual, 'Unknown error.' )

      # =================
      # Logical Operators
      # -----------------
      @LDefPrimitive( 'not', '<expr>')                                         # (not <val>)
      def LP_not( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_not, '1 argument exptected.' )

         arg1 = args[0]
         return 1 if ((arg1 == 0) or ((isinstance(arg1,LList) and len(arg1._list)==0)) or (arg1 is None)) else 0

      @LDefPrimitive( 'and', '<expr1> <expr2> ...' )                           # (and <val1> <val2> ...)
      def LP_and( env, *args, **keys ):
         if len(args) < 2:
            raise LypsRuntimeFuncError( LP_and, '2 or more arguments exptected.' )

         for arg in args:
            if (arg == 0) or (arg is LNULL) or (arg is None):
               return 0

         return 1

      @LDefPrimitive( 'or', '<expr1> <expr2> ...' )                            # (or  <val1> <val2> ...)
      def LP_or( env, *args, **keys ):
         if len(args) < 2:
            raise LypsRuntimeFuncError( LP_or, '2 or more arguments exptected.' )

         for arg in args:
            if (arg != 0) and (arg is not LNULL) and (arg is not None):
               return 1

         return 0

      # ===============
      # Type Conversion
      # ---------------
      @LDefPrimitive( 'float', '<expr>')                                       # (float <val>)
      def LP_float( env, *args, **keys ):
         if len(args) != 1:
            raise LypsRuntimeFuncError( LP_float, 'Exactly 1 argument expected.' )

         try:
            return float(args[0])
         except:
            raise LypsRuntimeFuncError( LP_float, 'Invalid argument.' )

      @LDefPrimitive( 'string', '<expr1> <expr2> ...' )                        # (string <expr1> <expr2> ...)   ; returns the concatenation of the string results of the arguments
      def LP_string( env, *args, **keys ):
         if len(args) == 0:
            raise LypsRuntimeFuncError( LP_string, '1 or more arguments exptected.' )

         result = ''

         try:
            for arg in args:
               if isinstance( arg, str ):
                  result += '"' + arg + '"'
               else:
                  result += str( arg )
         except:
            raise LypsRuntimeFuncError( LP_string, 'Unknown error.' )

         return result

      # ===============
      # I/O
      # ---------------
      @LDefPrimitive( 'write!', '<object>')                                    # (write! <lypsObject>)
      def LP_write( env, *args, **keys ):
         numArgs = len(args)
         if numArgs != 1:
            raise LypsRuntimeFuncError( LP_write, '1 argument expected' )

         value  = args[0]

         print( prettyPrintLypsExpr(value), sep='', end='', file=L_STDOUT )

         return value

      @LDefPrimitive( 'writeLn!', '<object>')                                  # (writeLn! <lypsObject>)
      def LP_writeln( env, *args, **keys ):
         numArgs = len(args)
         if numArgs != 1:
            raise LypsRuntimeFuncError( LP_write, '1 argument expected' )

         value  = args[0]

         print( prettyPrintLypsExpr(value), sep='', end='\n' )

         return value

      @LDefPrimitive( 'readLn!', '')                                           # (readLn!)
      def LP_readLn( env, *args, **keys ):
         numArgs = len(args)
         if numArgs > 0:
            raise LypsRuntimeFuncError( LP_read, '0 arguments expected.' )

         return input()


      return primitiveDict
