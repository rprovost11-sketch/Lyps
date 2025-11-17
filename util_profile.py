from time import perf_counter as timer
from typing import List, Tuple


class PerfTimer( object ):
   STATS: List[Tuple[str, float]] = [ ]

   def __init__( self, title: str='### testing ###' ):
      self._title:str           = title
      self._startTime:int     = 0

   def __enter__( self ):
      self.totalTime      = 0
      self._startTime     = timer( )
      return self

   def __exit__( self, *exc ):
      endTime = timer( )
      totalTime = endTime - self._startTime
      PerfTimer.STATS.append( (self._title, totalTime) )

   @staticmethod
   def dump( ):
      for title,perf in PerfTimer.STATS:
         print( title )
         print( '   --- Performance test time:  {0:12.5f} Sec'.format(perf) )
         print( )

if __name__ == '__main__':
   numIterations = 1000

   testName = 'List element access: [0].'
   lst = [ 10*x for x in range(5000) ]
   with PerfTimer( testName ):
      for x in range(numIterations):
         y = lst[0]

   testName = 'List element access: [5000].'
   lst = [ 10*x for x in range(5000) ]
   with PerfTimer( testName ):
      for x in range(numIterations):
         y = lst[4999]

   PerfTimer.dump( )



