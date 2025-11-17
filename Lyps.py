import ltk_py3.Listener as Listener
from LypsInterpreter import LypsInterpreter

def main( ) -> None:
   interp = LypsInterpreter( )
   theListener = Listener.Listener( interp, language='Lyps',
                                            version='0.2.1',
                                            author='Ronald Provost')
   theListener.readEvalPrintLoop( )

if __name__ == '__main__':
   main( )
