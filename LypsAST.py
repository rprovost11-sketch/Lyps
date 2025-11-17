from ltk_py3.SymbolTable import SymbolTable

import fractions
from typing import Any, Dict, Callable

# #################
# Lyps Function API
def prettyPrintLypsExpr( lypsExpr: Any ) -> str:
   '''Return a printable, formatted python string representation
   of a lyps object.'''
   if isinstance(lypsExpr, str):
      return f'\"{lypsExpr}\"'
   elif isinstance(lypsExpr, fractions.Fraction):
      return f'{lypsExpr.numerator}/{lypsExpr.denominator}'
   else:
      return repr(lypsExpr)

# ###############################
# Lyps Runtime Object Definitions
class LSymbol( object ):
   def __init__( self, val: str ) -> None:
      self._val = val

   def __str__( self ) -> str:
      return self._val

   def __repr__( self ) -> str:
      return self._val

   def __eq__( self, other: Any ) -> bool:
      try:
         return self._val == other._val
      except AttributeError:
         return False

   def __ne__( self, other: Any ) -> bool:
      try:
         return self._val != other._val
      except:
         return True


class LList( object ):
   def __init__( self, *elements ) -> None:
      self._list = list(elements)

   def __getitem__( self, index: int ) -> Any:
      return self._list[ index ]

   def __len__( self ) -> int:
      return len(self._list)

   def __iter__( self ):
      return iter( self._list )

   def __str__( self ) -> str:
      if len(self._list) == 0:
         return 'NULL'

      mbrList = [ prettyPrintLypsExpr(mbr) for mbr in self._list ]
      mbrListStr = ' '.join(mbrList)
      resultStr = f'({mbrListStr})'
      return resultStr

   def __repr__( self ) -> str:
      if len(self._list) == 0:
         return 'NULL'

      mbrList = [ prettyPrintLypsExpr(mbr) for mbr in self._list ]
      mbrListStr = ' '.join(mbrList)
      resultStr = f'({mbrListStr})'
      return resultStr

   def __eq__( self, other: Any ) -> bool:
      '''
      (defun!! '(equal? expr1 expr2)
               '(cond '( ((or (isAtom? expr1)
                              (isNull? expr1))
                                       (= expr1 expr2))
                         ((and (isList? expr1)
                               (isList? expr2))
                                       (and (isList? expr2)
                                            (and (equal? (first expr1) (first expr2))
                                                 (equal? (rest expr1) (rest expr2)))))
                         (1
                                       null))))
      '''
      if not isinstance(other, LList):
         return False

      if len(self) != len(other):
         return False

      for subSelf, subOther in zip( self, other ):
         if subSelf != subOther:
            return False

      return True

   def copy( self ) -> LList:
      return LList( *self._list[:] )

   def insert( self, index: int, value: Any ) -> None:
      self._list.insert( index, value )

   def first( self ) -> Any:
      return self._list[ 0 ]

   def rest( self ) -> LList:
      if len(self._list) < 2:
         return LList( )
      else:
         return LList( *self._list[ 1 : ])


class LMap( object ):
   def __init__( self, aMap: (Dict[Any, Any]|None) = None ):
      self._dict: Dict[Any, Any] = aMap if aMap else { }

   def __str__( self ) -> str:
      resultStrLines = [ '(MAP\n' ]
      for key in sorted(self._dict.keys()):
         value = self._dict[key]
         key = str(key)
         value = str(value)
         resultStrLines.append( f'   ({key} {value})\n')
      resultStrLines.append(')\n')
      return ''.join(resultStrLines)

   def __repr__( self ) -> str:
      resultStrLines = [ '(MAP\n' ]
      for key in sorted(self._dict.keys()):
         value = self._dict[key]
         key = prettyPrintLypsExpr(key)
         value = prettyPrintLypsExpr(value)
         resultStrLines.append( f'   ({key} {value})\n')
      resultStrLines.append(')\n')
      return ''.join(resultStrLines)

   def __setitem__( self, key: Any, val: Any ) -> None:
      if isinstance( key, LSymbol ):
         self._dict[ key._val ] = val
      else:
         self._dict[ key ] = val

   def __getitem__( self, key: Any ) -> Any:
      if isinstance( key, LSymbol ):
         return self._dict[ key._val ]
      else:
         return self._dict[ key ]


class LFunction( object ):
   def __init__( self, name: LSymbol, params: LList, bodyExprLst: LList ) -> None:
      self._name: LSymbol   = name
      self._params: LList = params
      self._body: LList   = bodyExprLst
      self._stdEvalOrd:bool = True

      self.setName( name )

   def __str__( self ) -> str:
      return self._reprStr

   def __repr__( self ) -> str:
      return self._reprStr

   def __call__( self, lypsExprEvaluator: Callable[[SymbolTable, Any], Any], env: SymbolTable, *args, **keys ) -> Any:
      return lypsExprEvaluator( env, self, *args, **keys )

   def setName( self, name: LSymbol ) -> None:
      paramList = [ x._val for x in self._params ]
      paramListStr = ' '.join(paramList)
      self._reprStr = f"(Function {self._name} ({paramListStr}) ... )"


class LPrimitive( object ):
   def __init__( self, fn: Callable[[SymbolTable], Any], name: str, usage: str, stdEvalOrd: bool=True ) -> None:
      self._fn:Callable[[SymbolTable], Any] = fn
      self._name:str = name
      #self.__lname__:str = name
      self._usage:str = usage
      self._stdEvalOrd:bool = stdEvalOrd

   def __call__( self, lypsExprEvaluator: Callable[[SymbolTable, Any], Any], env: SymbolTable, *args, **keys ) -> Any:
      return self._fn( env, *args, **keys )


class LMacro( object ):
   def __init__( self, name: LSymbol, params: LList, bodyExprList: LList ) -> None:
      self._name: LSymbol = name
      self._params: LList = params
      self._body: LList = bodyExprList
      self._stdEvalOrd: bool = False

      self.setName( name )

   def __str__( self ) -> str:
      return self._reprStr

   def __repr__( self ) -> str:
      return self._reprStr

   def __call__( self, lypsExprEvaluator: Callable[[SymbolTable, Any], Any], env: SymbolTable, *args, **keys ) -> Any:
      return lypsExprEvaluator( env, self, *args, **keys )

   def setName( self, name: LSymbol ) -> None:
      paramList = [ x._val for x in self._params ]
      paramListStr = ' '.join(paramList)
      self._reprStr = f"(Macro {self._name} ({paramListStr}) ... )"
