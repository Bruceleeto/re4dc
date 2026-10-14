"""freeze.py <epoch> <script> [args...]: run a staging script with time.time() frozen (pycdlib stamps the wall clock
into directory records and the volume descriptor), so two stagings of the same inputs can be compared byte for byte.
Proof runs only (lane stage-ext4)."""
import runpy, sys, time
t = float(sys.argv[1])
time.time = lambda: t
sys.argv = sys.argv[2:]
runpy.run_path(sys.argv[0], run_name='__main__')
