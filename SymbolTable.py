from typing import Any, List, Dict

class SymbolTable( object ):
   GLOBAL_SCOPE: (SymbolTable | None) = None

   def __init__( self, parent: (SymbolTable|None)=None, **initialNameValDict):
      self._parent: (SymbolTable | None) = parent
      self._locals: Dict[str, Any] = initialNameValDict.copy()
      if SymbolTable.GLOBAL_SCOPE is None:
         SymbolTable.GLOBAL_SCOPE = self

   def reInitialize( self, **initialNameValDict ) -> SymbolTable:
      root = SymbolTable.GLOBAL_SCOPE
      assert isinstance(root, SymbolTable)
      root._locals = initialNameValDict.copy()
      return root

   def defLocal( self, key: str, value: Any ) -> Any:
      self._locals[ key ] = value
      return value

   def defGlobal( self, key: str, value: Any ) -> Any:
      assert isinstance(SymbolTable.GLOBAL_SCOPE, SymbolTable)
      SymbolTable.GLOBAL_SCOPE._locals[ key ] = value
      return value

   def getValue( self, key: str ) -> Any:
      scope: (SymbolTable | None) = self
      while scope:
         try:
            return scope._locals[ key ]
         except KeyError:
            scope = scope._parent

      return None

   def getGlobalValue(self, key: str ) -> Any:
      assert isinstance(self.GLOBAL_SCOPE, SymbolTable)
      return self.GLOBAL_SCOPE._locals[ key ]

   def undef( self, key: str ) -> None:
      scope: (SymbolTable | None) = self
      while scope:
         try:
            del scope._locals[ key ]
            return
         except KeyError:
            scope = scope._parent

   def localSymbols( self ) -> List[str]:
      return sorted( self._locals.keys() )

   def parentEnv( self ) -> (SymbolTable | None):
      return self._parent

   def openScope( self ) -> SymbolTable:
      return SymbolTable( self )

   def closeScope( self ) -> (SymbolTable | None):
      return self._parent

   def isDefined( self, key: str ) -> bool:
      scope: (SymbolTable | None) = self
      while scope:
         if key in scope._locals:
            return True

         scope = scope._parent

      return False

   def findDef( self, key: str ) -> (SymbolTable | None):
      '''Starting from the local-most scope, this function searches for the
      scope in which a symbol (key) is defined and returns that SymbolTable.
      If the key is not defined, None is returned.'''
      scope: (SymbolTable | None) = self
      while scope:
         if key in scope._locals:
            return scope

         scope = scope._parent

      return None
